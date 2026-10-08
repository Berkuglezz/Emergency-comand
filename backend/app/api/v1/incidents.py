import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import CurrentUserDep, IncidentServiceDep, require_permission
from app.core.permissions import Permission
from app.domain.enums import IncidentPriority, IncidentStatus
from app.domain.incident_rules import allowed_transitions
from app.models import IncidentEvent, User
from app.repositories.incidents import IncidentListQuery
from app.schemas.errors import ErrorResponse
from app.schemas.incidents import (
    EventActor,
    IncidentCreate,
    IncidentDetail,
    IncidentEventResponse,
    IncidentNoteCreate,
    IncidentPage,
    IncidentRef,
    IncidentSort,
    IncidentStatusChange,
    IncidentSummary,
    IncidentTypeResponse,
    IncidentUpdate,
)
from app.services.incidents import IncidentView

_ERRORS: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}

_READ = [Depends(require_permission(Permission.INCIDENTS_READ))]
_CREATE = [Depends(require_permission(Permission.INCIDENTS_CREATE))]
_UPDATE = [Depends(require_permission(Permission.INCIDENTS_UPDATE))]

types_router = APIRouter(prefix="/incident-types", tags=["incidents"], responses=_ERRORS)
router = APIRouter(prefix="/incidents", tags=["incidents"], responses=_ERRORS)


def _detail(view: IncidentView) -> IncidentDetail:
    incident = view.incident
    summary = IncidentSummary.model_validate(incident)
    return IncidentDetail(
        **summary.model_dump(),
        description=incident.description,
        details=incident.details,
        parent=IncidentRef.model_validate(incident.parent) if incident.parent else None,
        children=[IncidentRef.model_validate(child) for child in view.children],
        closed_at=incident.closed_at,
        created_at=incident.created_at,
        allowed_transitions=allowed_transitions(incident.status),
    )


def _event(event: IncidentEvent, actor: User | None) -> IncidentEventResponse:
    return IncidentEventResponse(
        id=event.id,
        event_type=event.event_type,
        occurred_at=event.occurred_at,
        actor=EventActor(id=actor.id, full_name=actor.full_name) if actor else None,
        payload=event.payload,
        is_simulated=event.is_simulated,
    )


@types_router.get("", dependencies=_READ)
async def list_incident_types(service: IncidentServiceDep) -> list[IncidentTypeResponse]:
    return [IncidentTypeResponse.model_validate(t) for t in await service.list_types()]


@router.get("", dependencies=_READ)
async def list_incidents(
    service: IncidentServiceDep,
    status_filter: Annotated[list[IncidentStatus] | None, Query(alias="status")] = None,
    priority: Annotated[list[IncidentPriority] | None, Query()] = None,
    type_code: Annotated[str | None, Query(alias="type", max_length=64)] = None,
    active: bool = True,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    parent_id: uuid.UUID | None = None,
    sort: IncidentSort = "priority",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> IncidentPage:
    """Incidentes. Por defecto solo los activos (`active=false` incluye cerrados y cancelados)."""
    query = IncidentListQuery(
        statuses=status_filter or (),
        priorities=priority or (),
        type_code=type_code,
        active_only=active,
        search=q,
        parent_id=parent_id,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    items, total = await service.list_incidents(query)
    return IncidentPage(
        items=[IncidentSummary.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=_CREATE)
async def create_incident(
    body: IncidentCreate, user: CurrentUserDep, service: IncidentServiceDep
) -> IncidentDetail:
    return _detail(await service.create_incident(body, user))


@router.get("/{incident_id}", dependencies=_READ)
async def get_incident(incident_id: uuid.UUID, service: IncidentServiceDep) -> IncidentDetail:
    return _detail(await service.get_incident(incident_id))


@router.patch("/{incident_id}", dependencies=_UPDATE)
async def update_incident(
    incident_id: uuid.UUID, body: IncidentUpdate, user: CurrentUserDep, service: IncidentServiceDep
) -> IncidentDetail:
    return _detail(await service.update_incident(incident_id, body, user))


@router.post("/{incident_id}/status", dependencies=_UPDATE)
async def change_incident_status(
    incident_id: uuid.UUID,
    body: IncidentStatusChange,
    user: CurrentUserDep,
    service: IncidentServiceDep,
) -> IncidentDetail:
    """Cambia el estado. Cerrar o cancelar exige además `incidents:close`."""
    return _detail(await service.change_status(incident_id, body, user))


@router.get("/{incident_id}/events", dependencies=_READ)
async def list_incident_events(
    incident_id: uuid.UUID, service: IncidentServiceDep
) -> list[IncidentEventResponse]:
    """Historial funcional del incidente (timeline), en orden cronológico."""
    return [_event(event, actor) for event, actor in await service.list_events(incident_id)]


@router.post("/{incident_id}/notes", status_code=status.HTTP_201_CREATED, dependencies=_UPDATE)
async def add_incident_note(
    incident_id: uuid.UUID,
    body: IncidentNoteCreate,
    user: CurrentUserDep,
    service: IncidentServiceDep,
) -> IncidentEventResponse:
    return _event(await service.add_note(incident_id, body, user), user)
