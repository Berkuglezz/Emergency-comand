"""Lógica de negocio de incidentes.

Cada operación de escritura modifica el incidente e inserta sus entradas de
historial (`IncidentEvent`) en la misma transacción, con un único commit: si
algo falla, no queda ni el cambio ni el evento.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import Permission, has_permission
from app.domain.enums import IncidentEventType
from app.domain.exceptions import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    PermissionDeniedError,
)
from app.domain.incident_details import validate_details
from app.domain.incident_rules import (
    CLOSING_STATUSES,
    INITIAL_STATUS,
    TERMINAL_STATUSES,
    can_transition,
)
from app.models import Incident, IncidentEvent, IncidentType, Location, User
from app.repositories.incidents import IncidentListQuery, IncidentRepository
from app.schemas.incidents import (
    IncidentCreate,
    IncidentNoteCreate,
    IncidentStatusChange,
    IncidentUpdate,
    LocationInput,
)
from app.services.transactions import commit_or_conflict

# Campos editables sin evento propio (se agrupan en `incident_updated`).
_PLAIN_FIELDS = ("title", "description", "affected_people")
# Campos que no admiten `null` en una edición parcial.
_NOT_NULLABLE = frozenset({"title", "location", "priority", "details"})


@dataclass(frozen=True, slots=True)
class IncidentView:
    incident: Incident
    children: Sequence[Incident]


class _EventRecorder:
    """Inserta las entradas de historial de una operación, todas con la hora
    real en que se produjo. El timeline se ordena por `(occurred_at, id)`."""

    def __init__(self, repository: IncidentRepository, actor: User, now: datetime) -> None:
        self._repository = repository
        self._actor = actor
        self._now = now

    def record(
        self, incident: Incident, event_type: IncidentEventType, payload: dict[str, Any]
    ) -> IncidentEvent:
        event = IncidentEvent(
            incident_id=incident.id,
            event_type=event_type,
            occurred_at=self._now,
            actor_user_id=self._actor.id,
            payload=payload,
            is_simulated=incident.is_simulated,
        )
        self._repository.add_event(event)
        return event


def _apply_location(location: Location, data: LocationInput) -> list[str]:
    """Sustituye la ubicación completa. Devuelve los campos que cambiaron, con
    los nombres que ya usa el historial (`municipality`, `location_description`)."""
    changed: list[str] = []
    description = data.description or None  # cadena vacía = sin valor
    if location.municipality != data.municipality:
        location.municipality = data.municipality
        changed.append("municipality")
    if location.description != description:
        location.description = description
        changed.append("location_description")
    return changed


class IncidentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._incidents = IncidentRepository(session)

    # --- Consultas --------------------------------------------------------------

    async def list_types(self) -> Sequence[IncidentType]:
        return await self._incidents.list_types()

    async def list_incidents(self, query: IncidentListQuery) -> tuple[Sequence[Incident], int]:
        return await self._incidents.list(query)

    async def get_incident(self, incident_id: uuid.UUID) -> IncidentView:
        incident = await self._incidents.get(incident_id)
        if incident is None:
            raise NotFoundError("incident_not_found")
        return IncidentView(incident, await self._incidents.children(incident.id))

    async def list_events(
        self, incident_id: uuid.UUID
    ) -> Sequence[tuple[IncidentEvent, User | None]]:
        if await self._incidents.get(incident_id) is None:
            raise NotFoundError("incident_not_found")
        return await self._incidents.list_events(incident_id)

    # --- Escritura ----------------------------------------------------------------

    async def create_incident(self, data: IncidentCreate, actor: User) -> IncidentView:
        incident_type = await self._incidents.get_type(data.type_id)
        if incident_type is None or not incident_type.is_active:
            raise InvalidInputError("incident_type_not_found")
        details = validate_details(incident_type.details_schema_key, data.details)
        parent = await self._validate_parent(None, data.parent_incident_id)

        now = datetime.now(UTC)
        incident = Incident(
            code=await self._incidents.next_code(),
            type_id=incident_type.id,
            title=data.title,
            description=data.description or None,
            status=INITIAL_STATUS,
            priority=data.priority or incident_type.default_priority,
            location=Location(
                municipality=data.location.municipality,
                description=data.location.description or None,
            ),
            affected_people=data.affected_people,
            details=details,
            parent_incident_id=parent.id if parent else None,
            created_by_id=actor.id,
            is_simulated=False,
            reported_at=now,
        )
        self._incidents.add(incident)
        await self._session.flush()

        _EventRecorder(self._incidents, actor, now).record(
            incident,
            IncidentEventType.INCIDENT_CREATED,
            {
                "status": incident.status,
                "priority": incident.priority,
                "type": incident_type.code,
                "parent": parent.code if parent else None,
            },
        )
        await self._commit()
        return await self.get_incident(incident.id)

    async def update_incident(
        self, incident_id: uuid.UUID, data: IncidentUpdate, actor: User
    ) -> IncidentView:
        """Edición parcial. Si ningún valor cambia de verdad, no se escribe nada:
        ni `IncidentEvent` ni incremento de `version`."""
        incident = await self._load_for_change(incident_id, data.version)
        if incident.status in TERMINAL_STATUSES:
            raise InvalidInputError("incident_closed")

        sent = data.model_fields_set - {"version"}
        if any(getattr(data, name) is None for name in sent & _NOT_NULLABLE):
            raise InvalidInputError("field_not_nullable")

        now = datetime.now(UTC)
        events = _EventRecorder(self._incidents, actor, now)

        # El padre se valida (consulta) antes de modificar nada: así el autoflush
        # no emite un UPDATE intermedio y `version` sube una sola vez.
        if "parent_incident_id" in sent and data.parent_incident_id != incident.parent_incident_id:
            new_parent = await self._validate_parent(incident.id, data.parent_incident_id)
            events.record(
                incident,
                IncidentEventType.PARENT_CHANGED,
                {
                    "from": incident.parent.code if incident.parent else None,
                    "to": new_parent.code if new_parent else None,
                },
            )
            incident.parent_incident_id = new_parent.id if new_parent else None

        if "priority" in sent and data.priority is not None and data.priority != incident.priority:
            events.record(
                incident,
                IncidentEventType.PRIORITY_CHANGED,
                {"from": incident.priority, "to": data.priority},
            )
            incident.priority = data.priority

        changed: list[str] = []
        for name in _PLAIN_FIELDS:
            if name in sent:
                value = getattr(data, name)
                if isinstance(value, str) and not value and name != "title":
                    value = None  # cadena vacía en un campo opcional = sin valor
                if getattr(incident, name) != value:
                    setattr(incident, name, value)
                    changed.append(name)
        location_edited = False
        if "location" in sent and data.location is not None:
            location_fields = _apply_location(incident.location, data.location)
            changed.extend(location_fields)
            location_edited = bool(location_fields)
        if "details" in sent and data.details is not None:
            details = validate_details(incident.type.details_schema_key, data.details)
            if details != incident.details:
                incident.details = details
                changed.append("details")
        if changed:
            events.record(incident, IncidentEventType.INCIDENT_UPDATED, {"fields": sorted(changed)})
        if location_edited:
            # La ubicación vive en otra tabla: sin tocar la fila del incidente,
            # `version` no subiría y el bloqueo optimista no cubriría el cambio.
            incident.updated_at = now

        await self._commit()
        return await self.get_incident(incident.id)

    async def change_status(
        self, incident_id: uuid.UUID, data: IncidentStatusChange, actor: User
    ) -> IncidentView:
        incident = await self._load_for_change(incident_id, data.version)
        target = data.status
        if not can_transition(incident.status, target):
            raise InvalidInputError("invalid_transition")
        # Cerrar o cancelar exige un permiso propio: depende del estado de destino.
        if target in CLOSING_STATUSES and not has_permission(
            actor.role.code, Permission.INCIDENTS_CLOSE
        ):
            raise PermissionDeniedError()

        now = datetime.now(UTC)
        previous = incident.status
        incident.status = target
        incident.closed_at = now if target in TERMINAL_STATUSES else None
        payload: dict[str, Any] = {"from": previous, "to": target}
        if data.reason:
            payload["reason"] = data.reason
        _EventRecorder(self._incidents, actor, now).record(
            incident, IncidentEventType.STATUS_CHANGED, payload
        )
        await self._commit()
        return await self.get_incident(incident.id)

    async def add_note(
        self, incident_id: uuid.UUID, data: IncidentNoteCreate, actor: User
    ) -> IncidentEvent:
        incident = await self._incidents.get(incident_id)
        if incident is None:
            raise NotFoundError("incident_not_found")
        event = _EventRecorder(self._incidents, actor, datetime.now(UTC)).record(
            incident, IncidentEventType.NOTE_ADDED, {"text": data.text}
        )
        await self._commit()
        return event

    # --- Internos -----------------------------------------------------------------

    async def _load_for_change(self, incident_id: uuid.UUID, version: int) -> Incident:
        # FOR UPDATE: dos cambios simultáneos sobre el mismo incidente se serializan.
        incident = await self._incidents.get(incident_id, for_update=True)
        if incident is None:
            raise NotFoundError("incident_not_found")
        if incident.version != version:
            raise ConflictError("version_conflict")
        return incident

    async def _validate_parent(
        self, incident_id: uuid.UUID | None, parent_id: uuid.UUID | None
    ) -> Incident | None:
        """Un único nivel de jerarquía: padre → hijo."""
        if parent_id is None:
            return None
        if parent_id == incident_id:
            raise InvalidInputError("invalid_parent")
        parent = await self._incidents.get(parent_id)
        # El padre no puede ser a su vez hijo de otro incidente.
        if parent is None or parent.parent_incident_id is not None:
            raise InvalidInputError("invalid_parent")
        # Un incidente con hijos no puede convertirse en hijo.
        if incident_id is not None and await self._incidents.has_children(incident_id):
            raise InvalidInputError("invalid_parent")
        return parent

    async def _commit(self) -> None:
        await commit_or_conflict(self._session)
