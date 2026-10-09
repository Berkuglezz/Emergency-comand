"""Asignación de recursos a incidentes (CLAUDE.md §2.8).

El sistema informa (candidatos ordenados por ETA estimada), la persona
responsable decide y el sistema ejecuta. Nada se asigna automáticamente.

Cada operación cambia, en una sola transacción, la asignación, el estado del
recurso, el incidente (su `version` sube una vez y, si procede, su estado) y su
historial (`IncidentEvent`).

Orden global de bloqueos `FOR UPDATE`, el mismo en todas las operaciones (y en
el cierre de incidentes), para que dos operaciones concurrentes nunca se
esperen en círculo: **incidentes (por id) → recursos (por id) → asignaciones**.
Con el incidente bloqueado, sus asignaciones activas no pueden cambiar: toda
operación que las toca bloquea antes ese incidente.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.access_scope import AccessScope
from app.domain.assignment_rules import (
    USER_RELEASE_REASONS,
    assignment_blocker,
    resource_status_after_release,
)
from app.domain.enums import (
    IncidentEventType,
    IncidentStatus,
    ReleaseReason,
    ResourceStatus,
    StatusChangeCause,
)
from app.domain.eta import Eta, EtaUnavailable, estimate
from app.domain.exceptions import ConflictError, InvalidInputError, NotFoundError
from app.domain.incident_rules import (
    TERMINAL_STATUSES,
    status_after_assignment,
    status_after_last_release,
)
from app.models import Incident, Resource, ResourceAssignment, User
from app.repositories.assignments import AssignmentRepository
from app.repositories.incidents import IncidentRepository
from app.repositories.resources import ResourceRepository
from app.schemas.assignments import AssignmentArrival, AssignmentCreate, AssignmentRelease
from app.services.incident_events import EventRecorder
from app.services.transactions import commit_or_conflict

# Índice único parcial: un recurso solo tiene una asignación activa.
_ACTIVE_RESOURCE_INDEX = "uq_resource_assignments_active_resource"


@dataclass(frozen=True, slots=True)
class Candidate:
    resource: Resource
    eta: Eta | EtaUnavailable
    suggested: bool
    # Incidente al que ya está asignado (solo si se pidieron los asignados).
    current_incident: tuple[uuid.UUID, str] | None


def eta_for(resource: Resource, incident: Incident) -> Eta | EtaUnavailable:
    """ETA estimada desde la base del recurso hasta el incidente."""
    base, location = resource.base, incident.location
    origin = (
        (base.latitude, base.longitude)
        if base.latitude is not None and base.longitude is not None
        else None
    )
    destination = (
        (location.latitude, location.longitude)
        if location.latitude is not None and location.longitude is not None
        else None
    )
    return estimate(origin, destination, resource.type.average_speed_kmh)


def _eta_payload(eta: Eta | EtaUnavailable) -> dict[str, Any] | None:
    if isinstance(eta, EtaUnavailable):
        return None
    return {"minutes": eta.minutes, "distance_km": eta.distance_km, "origin": eta.origin}


def _set_status(incident: Incident, target: IncidentStatus, events: EventRecorder) -> None:
    """Cambio de estado automático, registrado con su causa."""
    if target == incident.status:
        return
    events.record(
        incident,
        IncidentEventType.STATUS_CHANGED,
        {"from": incident.status, "to": target, "cause": StatusChangeCause.ASSIGNMENT},
    )
    incident.status = target


def release(
    assignment: ResourceAssignment,
    incident: Incident,
    resource: Resource,
    reason: ReleaseReason,
    *,
    actor: User,
    events: EventRecorder,
    now: datetime,
    remaining_active: int | None,
    reassigned_to: str | None = None,
) -> None:
    """Retira un recurso. `remaining_active`: asignaciones activas que le quedan
    al incidente después de esta; `None` = no aplicar la regla de estado (p. ej.
    al cerrar el incidente, que ya cambia de estado por sí mismo)."""
    assignment.released_at = now
    assignment.released_by_id = actor.id
    assignment.release_reason = reason
    resource.status = resource_status_after_release(reason)
    resource.status_changed_at = now
    events.record(
        incident,
        IncidentEventType.RESOURCE_RELEASED,
        {
            "resource": resource.code,
            "resource_id": str(resource.id),
            "reason": reason,
            "reassigned_to": reassigned_to,
        },
    )
    if remaining_active == 0:
        _set_status(incident, status_after_last_release(incident.status), events)


class AssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._incidents = IncidentRepository(session)
        self._resources = ResourceRepository(session)
        self._assignments = AssignmentRepository(session)

    # --- Consultas --------------------------------------------------------------

    async def list_for_incident(self, incident_id: uuid.UUID) -> Sequence[ResourceAssignment]:
        if await self._incidents.get(incident_id) is None:
            raise NotFoundError("incident_not_found")
        return await self._assignments.list_for_incident(incident_id)

    async def candidates(
        self,
        incident_id: uuid.UUID,
        *,
        type_code: str | None,
        organization_id: uuid.UUID | None,
        include_assigned: bool,
        scope: AccessScope,
    ) -> list[Candidate]:
        """Recursos asignables ordenados por ETA estimada (sin estimación, al
        final). Es ayuda a la decisión: no se preselecciona ninguno. Solo
        recursos del ámbito de escritura: los que el usuario podría asignar."""
        incident = await self._incidents.get(incident_id)
        if incident is None:
            raise NotFoundError("incident_not_found")
        resources = await self._assignments.candidate_resources(
            type_code=type_code,
            organization_id=organization_id,
            organization_ids=scope.write.as_filter(),
        )
        current = await self._assignments.current_for_resources(r.id for r in resources)
        suggested_types = set(incident.type.suggested_resource_types)

        candidates: list[Candidate] = []
        for resource in resources:
            assigned = current.get(resource.id)
            if assigned is not None:
                assignment, code = assigned
                # Ya está en este incidente, o en otro y no se pidieron los asignados.
                if assignment.incident_id == incident.id or not include_assigned:
                    continue
                current_incident: tuple[uuid.UUID, str] | None = (assignment.incident_id, code)
            else:
                if resource.status != ResourceStatus.AVAILABLE:
                    continue
                current_incident = None
            candidates.append(
                Candidate(
                    resource=resource,
                    eta=eta_for(resource, incident),
                    suggested=resource.type.code in suggested_types,
                    current_incident=current_incident,
                )
            )
        candidates.sort(
            key=lambda c: (
                isinstance(c.eta, EtaUnavailable),
                c.eta.minutes if isinstance(c.eta, Eta) else 0,
                c.resource.code,
            )
        )
        return candidates

    # --- Escritura ----------------------------------------------------------------

    async def assign(
        self, incident_id: uuid.UUID, data: AssignmentCreate, actor: User, scope: AccessScope
    ) -> uuid.UUID:
        """Asigna (o reasigna) un recurso. Devuelve el id del incidente.

        El recurso debe estar en el ámbito de escritura del usuario (CLAUDE.md
        §2.11, R.5); se comprueba tras bloquearlo y antes de modificar nada."""
        # Para respetar el orden de bloqueos, primero se mira (sin bloquear) a qué
        # incidente está asignado el recurso; se bloquean los incidentes
        # implicados y después todo se vuelve a comprobar con los bloqueos tomados.
        peek = await self._assignments.active_for_resource(data.resource_id)
        involved = {incident_id}
        if peek is not None and data.reassign:
            involved.add(peek.incident_id)
        locked = await self._lock_incidents(involved)
        incident = self._check_target(locked.get(incident_id), data.version)
        resource = await self._resources.get(data.resource_id, for_update=True)
        if resource is None:
            raise NotFoundError("resource_not_found")
        scope.require_write(resource.organization_id)
        current = await self._assignments.active_for_resource(resource.id, for_update=True)
        now = datetime.now(UTC)
        events = EventRecorder(self._incidents, actor, now)

        reassigned_from: str | None = None
        if current is not None:
            if current.incident_id == incident.id or not data.reassign:
                raise ConflictError("resource_already_assigned")
            origin = locked.get(current.incident_id)
            if origin is None:
                # Entretanto pasó a otro incidente que no está bloqueado: no se
                # toca nada y quien asigna vuelve a mirar el estado actual.
                raise ConflictError("resource_already_assigned")
            # Reasignación: se retira del incidente de origen en la misma transacción.
            origin_active = await self._assignments.active_for_incident(origin.id)
            origin_events = EventRecorder(self._incidents, actor, now)
            release(
                current,
                origin,
                resource,
                ReleaseReason.REASSIGNED,
                actor=actor,
                events=origin_events,
                now=now,
                remaining_active=len(origin_active) - 1,
                reassigned_to=incident.code,
            )
            origin.updated_at = now
            reassigned_from = origin.code
        else:
            blocker = assignment_blocker(is_active=resource.is_active, status=resource.status)
            if blocker is not None:
                raise InvalidInputError(blocker)

        eta = eta_for(resource, incident)
        self._assignments.add(
            ResourceAssignment(
                incident_id=incident.id,
                resource_id=resource.id,
                assigned_at=now,
                assigned_by_id=actor.id,
                eta_minutes=eta.minutes if isinstance(eta, Eta) else None,
                eta_distance_km=Decimal(str(eta.distance_km)) if isinstance(eta, Eta) else None,
                eta_origin=eta.origin if isinstance(eta, Eta) else None,
                is_simulated=incident.is_simulated,
            )
        )
        resource.status = ResourceStatus.IN_SERVICE
        resource.status_changed_at = now
        events.record(
            incident,
            IncidentEventType.RESOURCE_ASSIGNED,
            {
                "resource": resource.code,
                "resource_id": str(resource.id),
                "resource_type": resource.type.code,
                "eta": _eta_payload(eta),
                "eta_unavailable": eta if isinstance(eta, EtaUnavailable) else None,
                "reassigned_from": reassigned_from,
            },
        )
        _set_status(incident, status_after_assignment(incident.status), events)
        incident.updated_at = now
        await self._commit()
        return incident.id

    async def arrive(
        self, assignment_id: uuid.UUID, data: AssignmentArrival, actor: User, scope: AccessScope
    ) -> uuid.UUID:
        """Marca que el recurso ha llegado. No cambia el estado del incidente.

        Solo para recursos dentro del ámbito de escritura del usuario
        (CLAUDE.md §2.11, D9 y R.4), comprobado antes de modificar nada."""
        assignment, incident = await self._load_assignment(assignment_id, data.version)
        resource = await self._resources.get(assignment.resource_id)
        if resource is None:  # pragma: no cover — lo impide la clave foránea
            raise NotFoundError("resource_not_found")
        scope.require_write(resource.organization_id)
        if assignment.arrived_at is not None:
            raise InvalidInputError("assignment_already_arrived")
        now = datetime.now(UTC)
        assignment.arrived_at = now
        EventRecorder(self._incidents, actor, now).record(
            incident,
            IncidentEventType.RESOURCE_ARRIVED,
            {"resource": resource.code, "resource_id": str(resource.id)},
        )
        incident.updated_at = now
        await self._commit()
        return incident.id

    async def release(
        self, assignment_id: uuid.UUID, data: AssignmentRelease, actor: User, scope: AccessScope
    ) -> uuid.UUID:
        """Retira un recurso con un motivo elegido por la persona. El recurso debe
        estar en el ámbito de escritura del usuario (R.5)."""
        if data.reason not in USER_RELEASE_REASONS:
            raise InvalidInputError("invalid_release_reason")
        assignment, incident = await self._load_assignment(assignment_id, data.version)
        resource = await self._resources.get(assignment.resource_id, for_update=True)
        if resource is None:  # pragma: no cover — lo impide la clave foránea
            raise NotFoundError("resource_not_found")
        scope.require_write(resource.organization_id)
        active = await self._assignments.active_for_incident(incident.id)
        now = datetime.now(UTC)
        release(
            assignment,
            incident,
            resource,
            data.reason,
            actor=actor,
            events=EventRecorder(self._incidents, actor, now),
            now=now,
            remaining_active=len(active) - 1,
        )
        incident.updated_at = now
        await self._commit()
        return incident.id

    # --- Internos -----------------------------------------------------------------

    async def _lock_incidents(self, ids: set[uuid.UUID]) -> dict[uuid.UUID, Incident]:
        """Bloquea varios incidentes en orden de id (orden global de bloqueos)."""
        locked: dict[uuid.UUID, Incident] = {}
        for incident_id in sorted(ids):
            incident = await self._incidents.get(incident_id, for_update=True)
            if incident is not None:
                locked[incident_id] = incident
        return locked

    @staticmethod
    def _check_target(incident: Incident | None, version: int) -> Incident:
        if incident is None:
            raise NotFoundError("incident_not_found")
        if incident.version != version:
            raise ConflictError("version_conflict")
        if incident.status in TERMINAL_STATUSES:
            raise InvalidInputError("incident_closed")
        return incident

    async def _load_incident(self, incident_id: uuid.UUID, version: int) -> Incident:
        return self._check_target(await self._incidents.get(incident_id, for_update=True), version)

    async def _load_assignment(
        self, assignment_id: uuid.UUID, version: int
    ) -> tuple[ResourceAssignment, Incident]:
        found = await self._assignments.get(assignment_id)
        if found is None:
            raise NotFoundError("assignment_not_found")
        incident = await self._load_incident(found.incident_id, version)
        assignment = await self._assignments.get(assignment_id, for_update=True)
        if assignment is None:  # pragma: no cover — las asignaciones no se borran
            raise NotFoundError("assignment_not_found")
        if assignment.released_at is not None:
            raise InvalidInputError("assignment_already_released")
        return assignment, incident

    async def _commit(self) -> None:
        try:
            await commit_or_conflict(self._session)
        except IntegrityError as exc:
            await self._session.rollback()
            # Dos asignaciones simultáneas del mismo recurso: gana la primera.
            if _ACTIVE_RESOURCE_INDEX in str(exc.orig):
                raise ConflictError("resource_already_assigned") from exc
            raise


async def release_all_for_closing(
    session: AsyncSession,
    incident: Incident,
    *,
    actor: User,
    events: EventRecorder,
    now: datetime,
) -> None:
    """Retira todos los recursos activos de un incidente que se cierra o se
    cancela (`incident_closed`). La propia transición fija el estado final.

    El incidente ya está bloqueado, así que sus asignaciones activas no cambian:
    se bloquean sus recursos (por id) y después las asignaciones, en el orden
    global de bloqueos."""
    assignments = AssignmentRepository(session)
    resources = ResourceRepository(session)
    active = await assignments.active_for_incident(incident.id)
    locked: dict[uuid.UUID, Resource] = {}
    for resource_id in sorted(a.resource_id for a in active):
        resource = await resources.get(resource_id, for_update=True)
        if resource is None:  # pragma: no cover — lo impide la clave foránea
            raise NotFoundError("resource_not_found")
        locked[resource_id] = resource
    for assignment in await assignments.active_for_incident(incident.id, for_update=True):
        resource = locked[assignment.resource_id]
        release(
            assignment,
            incident,
            resource,
            ReleaseReason.INCIDENT_CLOSED,
            actor=actor,
            events=events,
            now=now,
            remaining_active=None,
        )
