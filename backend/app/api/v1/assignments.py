"""Asignación de recursos a incidentes (CLAUDE.md §2.8).

Las escrituras devuelven el detalle del incidente afectado, con su nueva
`version` y su estado.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import (
    AccessScopeDep,
    AssignmentServiceDep,
    CurrentUserDep,
    IncidentServiceDep,
    require_permission,
)
from app.api.v1.incidents import incident_detail
from app.api.v1.resources import assignment_eta
from app.core.permissions import Permission
from app.domain.eta import Eta, EtaUnavailable
from app.models import ResourceAssignment
from app.schemas.assignments import (
    AssignedResource,
    AssignmentArrival,
    AssignmentCandidate,
    AssignmentCreate,
    AssignmentRelease,
    AssignmentResponse,
    IncidentCodeRef,
)
from app.schemas.errors import ErrorResponse
from app.schemas.incidents import IncidentDetail
from app.schemas.resources import EtaResponse
from app.services.assignments import Candidate

_ERRORS: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}

_READ = [Depends(require_permission(Permission.INCIDENTS_READ))]
_CANDIDATES = [
    Depends(require_permission(Permission.INCIDENTS_READ)),
    Depends(require_permission(Permission.RESOURCES_READ)),
]
_MANAGE = [Depends(require_permission(Permission.ASSIGNMENTS_MANAGE))]
_UPDATE = [Depends(require_permission(Permission.ASSIGNMENTS_UPDATE))]

incident_router = APIRouter(prefix="/incidents", tags=["assignments"], responses=_ERRORS)
router = APIRouter(prefix="/assignments", tags=["assignments"], responses=_ERRORS)


def _assignment(assignment: ResourceAssignment) -> AssignmentResponse:
    return AssignmentResponse(
        id=assignment.id,
        incident_id=assignment.incident_id,
        resource=AssignedResource.model_validate(assignment.resource),
        assigned_at=assignment.assigned_at,
        arrived_at=assignment.arrived_at,
        released_at=assignment.released_at,
        release_reason=assignment.release_reason,
        eta=assignment_eta(assignment),
        is_simulated=assignment.is_simulated,
    )


def _candidate(candidate: Candidate) -> AssignmentCandidate:
    eta = candidate.eta
    return AssignmentCandidate(
        resource=AssignedResource.model_validate(candidate.resource),
        eta=(
            EtaResponse(minutes=eta.minutes, distance_km=eta.distance_km, origin=eta.origin)
            if isinstance(eta, Eta)
            else None
        ),
        eta_unavailable=eta if isinstance(eta, EtaUnavailable) else None,
        suggested=candidate.suggested,
        current_incident=(
            IncidentCodeRef(id=candidate.current_incident[0], code=candidate.current_incident[1])
            if candidate.current_incident
            else None
        ),
    )


@incident_router.get("/{incident_id}/assignments", dependencies=_READ)
async def list_incident_assignments(
    incident_id: uuid.UUID, service: AssignmentServiceDep
) -> list[AssignmentResponse]:
    """Asignaciones del incidente: activas primero y después el historial."""
    return [_assignment(a) for a in await service.list_for_incident(incident_id)]


@incident_router.get("/{incident_id}/assignment-candidates", dependencies=_CANDIDATES)
async def list_assignment_candidates(
    incident_id: uuid.UUID,
    scope: AccessScopeDep,
    service: AssignmentServiceDep,
    type_code: Annotated[str | None, Query(alias="type", max_length=64)] = None,
    organization_id: uuid.UUID | None = None,
    include_assigned: bool = False,
) -> list[AssignmentCandidate]:
    """Recursos asignables ordenados por ETA **estimada** (sin estimación, al final),
    con los tipos sugeridos marcados. Ayuda a la decisión: no se preselecciona ninguno.
    `include_assigned=true` añade los asignados a otros incidentes (exigen reasignar).
    Solo recursos del ámbito de escritura del usuario."""
    candidates = await service.candidates(
        incident_id,
        type_code=type_code,
        organization_id=organization_id,
        include_assigned=include_assigned,
        scope=scope,
    )
    return [_candidate(c) for c in candidates]


@incident_router.post("/{incident_id}/assignments", dependencies=_MANAGE)
async def assign_resource(
    incident_id: uuid.UUID,
    body: AssignmentCreate,
    user: CurrentUserDep,
    scope: AccessScopeDep,
    service: AssignmentServiceDep,
    incidents: IncidentServiceDep,
) -> IncidentDetail:
    """Asigna un recurso disponible. Con `reassign: true`, si está asignado a otro
    incidente, se retira de él y se asigna a este en la misma transacción.
    Recurso fuera del ámbito de escritura del usuario: 403 `organization_out_of_scope`."""
    affected = await service.assign(incident_id, body, user, scope)
    return incident_detail(await incidents.get_incident(affected))


@router.post("/{assignment_id}/arrival", dependencies=_UPDATE)
async def mark_arrival(
    assignment_id: uuid.UUID,
    body: AssignmentArrival,
    user: CurrentUserDep,
    scope: AccessScopeDep,
    service: AssignmentServiceDep,
    incidents: IncidentServiceDep,
) -> IncidentDetail:
    """Marca que el recurso ha llegado al lugar. No cambia el estado del incidente.
    Recurso fuera del ámbito de escritura del usuario: 403 `organization_out_of_scope`."""
    affected = await service.arrive(assignment_id, body, user, scope)
    return incident_detail(await incidents.get_incident(affected))


@router.post("/{assignment_id}/release", dependencies=_MANAGE)
async def release_resource(
    assignment_id: uuid.UUID,
    body: AssignmentRelease,
    user: CurrentUserDep,
    scope: AccessScopeDep,
    service: AssignmentServiceDep,
    incidents: IncidentServiceDep,
) -> IncidentDetail:
    """Retira el recurso con un motivo (`completed`, `not_needed` o `unavailable`).
    Recurso fuera del ámbito de escritura del usuario: 403 `organization_out_of_scope`."""
    affected = await service.release(assignment_id, body, user, scope)
    return incident_detail(await incidents.get_incident(affected))
