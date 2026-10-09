import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import CurrentUserDep, IncidentServiceDep, require_permission
from app.core.permissions import Permission
from app.domain.enums import IncidentPriority, IncidentStatus
from app.domain.geo import parse_bbox
from app.domain.incident_rules import allowed_transitions
from app.models import Incident, IncidentEvent, User
from app.repositories.incidents import IncidentListQuery
from app.schemas.errors import ErrorResponse
from app.schemas.incidents import (
    EventActor,
    IncidentCreate,
    IncidentDetail,
    IncidentEventResponse,
    IncidentMapCollection,
    IncidentMapFeature,
    IncidentMapProperties,
    IncidentNoteCreate,
    IncidentPage,
    IncidentRef,
    IncidentSort,
    IncidentStatusChange,
    IncidentSummary,
    IncidentTypeResponse,
    IncidentUpdate,
    PointGeometry,
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
# La edición exige al menos la operativa; los campos que no lo son exigen
# además `incidents:update`, y eso lo comprueba el servicio (depende del cuerpo).
_EDIT = [Depends(require_permission(Permission.INCIDENTS_UPDATE_OPERATIONAL))]
_CHANGE_STATUS = [Depends(require_permission(Permission.INCIDENTS_CHANGE_STATUS))]
_ANNOTATE = [Depends(require_permission(Permission.INCIDENTS_ANNOTATE))]

types_router = APIRouter(prefix="/incident-types", tags=["incidents"], responses=_ERRORS)
router = APIRouter(prefix="/incidents", tags=["incidents"], responses=_ERRORS)


def incident_detail(view: IncidentView) -> IncidentDetail:
    incident = view.incident
    summary = IncidentSummary.model_validate(incident).model_copy(
        update={"active_assignments": view.active_assignments}
    )
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


def _map_feature(incident: Incident) -> IncidentMapFeature:
    location = incident.location
    # Solo se llama con incidentes con coordenadas (lo garantiza la consulta).
    if location.latitude is None or location.longitude is None:  # pragma: no cover
        raise ValueError("incidente sin coordenadas en el mapa")
    return IncidentMapFeature(
        geometry=PointGeometry(coordinates=(location.longitude, location.latitude)),
        properties=IncidentMapProperties(
            id=incident.id,
            code=incident.code,
            title=incident.title,
            status=incident.status,
            priority=incident.priority,
            type_code=incident.type.code,
            type_icon=incident.type.icon,
            is_simulated=incident.is_simulated,
        ),
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
    has_coordinates: bool | None = None,
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
        has_coordinates=has_coordinates,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    items, total = await service.list_incidents(query)
    counts = await service.active_assignment_counts(items)
    return IncidentPage(
        items=[
            IncidentSummary.model_validate(item).model_copy(
                update={"active_assignments": counts.get(item.id, 0)}
            )
            for item in items
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/map", dependencies=_READ)
async def map_incidents(
    service: IncidentServiceDep,
    status_filter: Annotated[list[IncidentStatus] | None, Query(alias="status")] = None,
    priority: Annotated[list[IncidentPriority] | None, Query()] = None,
    active: bool = True,
    bbox: Annotated[
        str | None,
        Query(
            max_length=100,
            description="Rectángulo `minLon,minLat,maxLon,maxLat` (WGS84, orden GeoJSON).",
        ),
    ] = None,
) -> IncidentMapCollection:
    """Incidentes con coordenadas como `FeatureCollection` GeoJSON, con los mismos
    filtros de estado y prioridad que el listado (por defecto, solo activos).

    Datos mínimos para dibujar; el listado sigue siendo `GET /incidents`. Tope
    de 1.000 elementos (`truncated`); `unlocated_total` cuenta los que cumplen
    los filtros sin coordenadas."""
    query = IncidentListQuery(
        statuses=status_filter or (), priorities=priority or (), active_only=active
    )
    result = await service.map_incidents(query, parse_bbox(bbox) if bbox else None)
    return IncidentMapCollection(
        features=[_map_feature(incident) for incident in result.incidents],
        unlocated_total=result.unlocated_total,
        truncated=result.truncated,
    )


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=_CREATE)
async def create_incident(
    body: IncidentCreate, user: CurrentUserDep, service: IncidentServiceDep
) -> IncidentDetail:
    return incident_detail(await service.create_incident(body, user))


@router.get("/{incident_id}", dependencies=_READ)
async def get_incident(incident_id: uuid.UUID, service: IncidentServiceDep) -> IncidentDetail:
    return incident_detail(await service.get_incident(incident_id))


@router.patch("/{incident_id}", dependencies=_EDIT)
async def update_incident(
    incident_id: uuid.UUID, body: IncidentUpdate, user: CurrentUserDep, service: IncidentServiceDep
) -> IncidentDetail:
    return incident_detail(await service.update_incident(incident_id, body, user))


@router.post("/{incident_id}/status", dependencies=_CHANGE_STATUS)
async def change_incident_status(
    incident_id: uuid.UUID,
    body: IncidentStatusChange,
    user: CurrentUserDep,
    service: IncidentServiceDep,
) -> IncidentDetail:
    """Cambia el estado. Cerrar o cancelar exige además `incidents:close`."""
    return incident_detail(await service.change_status(incident_id, body, user))


@router.get("/{incident_id}/events", dependencies=_READ)
async def list_incident_events(
    incident_id: uuid.UUID, service: IncidentServiceDep
) -> list[IncidentEventResponse]:
    """Historial funcional del incidente (timeline), en orden cronológico."""
    return [_event(event, actor) for event, actor in await service.list_events(incident_id)]


@router.post("/{incident_id}/notes", status_code=status.HTTP_201_CREATED, dependencies=_ANNOTATE)
async def add_incident_note(
    incident_id: uuid.UUID,
    body: IncidentNoteCreate,
    user: CurrentUserDep,
    service: IncidentServiceDep,
) -> IncidentEventResponse:
    return _event(await service.add_note(incident_id, body, user), user)
