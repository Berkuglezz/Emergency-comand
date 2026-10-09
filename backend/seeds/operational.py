"""Seed de recursos e incidentes simulados (Fase 2).

A diferencia de usuarios y organizaciones, aquí el seed **solo crea lo que
falta y nunca modifica lo existente**: durante una demo se cambian estados,
prioridades o fichas, y volver a ejecutar el seed no debe deshacerlo.

- Ids fijos derivados de la clave del fixture (UUIDv5): el mismo dato tiene
  siempre el mismo id, en cualquier base de datos.
- Las horas son relativas al momento de la ejecución que crea cada fila.
- Cada incidente se crea con su historial completo (`IncidentEvent`),
  coherente con las reglas reales: transiciones (`can_transition`), `details`
  por tipo (`validate_details`) y coordenadas (`validate_coordinates`). Un
  fixture incoherente hace fallar el seed sin escribir nada.
- Un incidente que ya existe conserva su ubicación: una base de datos sembrada
  antes de la Fase 3.3 no recibe coordenadas (se reinicia con `down -v`).
- Las asignaciones simuladas siguen las mismas reglas que el servicio
  (cambios automáticos de estado, retirada al cerrar) y su ETA es la estimada
  desde la base del recurso.
- Todo lleva `is_simulated = true`. El actor de los eventos es nulo: los
  genera el sistema, no un usuario.
"""

import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    IncidentEventType,
    IncidentStatus,
    ReleaseReason,
    StatusChangeCause,
)
from app.domain.eta import Eta, EtaUnavailable, estimate
from app.domain.geo import validate_coordinates
from app.domain.incident_details import validate_details
from app.domain.incident_rules import (
    INITIAL_STATUS,
    TERMINAL_STATUSES,
    can_transition,
    status_after_assignment,
    status_after_last_release,
)
from app.models import (
    Incident,
    IncidentEvent,
    IncidentType,
    Location,
    Organization,
    Resource,
    ResourceAssignment,
    ResourceType,
)
from app.models.location import point
from app.repositories.incidents import IncidentRepository
from seeds.fixtures import INCIDENTS, RESOURCES, DemoIncident

RESOURCES_BY_CODE = {fixture.code: fixture for fixture in RESOURCES}

# Espacio de nombres de los UUIDv5 del seed (fijo: no cambiarlo nunca).
SEED_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "seed.demo.emergency-command.test")


def resource_id(code: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"resource:{code}")


def resource_base_id(code: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"resource:{code}:base")


def incident_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"incident:{key}")


def incident_location_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"incident:{key}:location")


def incident_assignment_id(key: str, index: int) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"incident:{key}:assignment:{index}")


def incident_event_id(key: str, index: int) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"incident:{key}:event:{index}")


async def seed_resources(
    session: AsyncSession, organizations: dict[str, Organization], now: datetime
) -> list[str]:
    ids = [resource_id(fixture.code) for fixture in RESOURCES]
    codes = [fixture.code for fixture in RESOURCES]
    existing = await _existing(
        session,
        select(Resource.id, Resource.code).where(
            or_(Resource.id.in_(ids), Resource.code.in_(codes))
        ),
    )
    types = await _by_code(session, ResourceType)

    created: list[str] = []
    for fixture in RESOURCES:
        # Ya existe (aunque se haya modificado o desactivado): no se toca.
        if resource_id(fixture.code) in existing or fixture.code in existing:
            continue
        # Misma regla que la API: una base fuera del área de la demo hace fallar el seed.
        latitude, longitude = fixture.base.coordinates
        validate_coordinates(latitude, longitude)
        # Si se borró el recurso, su base pudo quedar: se reutiliza tal cual.
        base = await session.get(Location, resource_base_id(fixture.code)) or Location(
            id=resource_base_id(fixture.code),
            municipality=fixture.base.municipality,
            description=fixture.base.description,
            geom=point(latitude, longitude),
        )
        session.add(
            Resource(
                id=resource_id(fixture.code),
                code=fixture.code,
                name=fixture.name,
                type_id=types[fixture.type_code].id,
                organization_id=organizations[fixture.organization_code].id,
                status=fixture.status,
                status_changed_at=now - timedelta(minutes=fixture.status_minutes_ago),
                base=base,
                is_simulated=True,
            )
        )
        created.append(f"resource:{fixture.code}")
    await session.flush()
    return created


async def seed_incidents(session: AsyncSession, now: datetime) -> list[str]:
    ids = [incident_id(fixture.key) for fixture in INCIDENTS]
    existing = await _existing(session, select(Incident.id).where(Incident.id.in_(ids)))
    types = await _by_code(session, IncidentType)
    resource_types = await _by_code(session, ResourceType)
    incidents = IncidentRepository(session)
    # Id real de cada recurso del seed por su código (un recurso creado a mano
    # con un código del seed conserva su id).
    resource_ids: dict[str, uuid.UUID] = {
        code: id_
        for code, id_ in await session.execute(
            select(Resource.code, Resource.id).where(Resource.code.in_(RESOURCES_BY_CODE))
        )
    }

    created: list[str] = []
    # Los códigos salen de la secuencia en el orden de los fixtures
    # (cronológico); el padre se crea siempre antes que sus hijos.
    for fixture in INCIDENTS:
        if incident_id(fixture.key) in existing:
            continue
        incident_type = types[fixture.type_code]
        reported_at = now - timedelta(minutes=fixture.reported_minutes_ago)
        coordinates = validate_coordinates(*fixture.coordinates) if fixture.coordinates else None

        def eta_for(
            code: str, destination: tuple[float, float] | None = coordinates
        ) -> Eta | EtaUnavailable:
            resource = RESOURCES_BY_CODE[code]
            speed = resource_types[resource.type_code].average_speed_kmh
            return estimate(resource.base.coordinates, destination, speed)

        history = _history(fixture, incident_type.code, reported_at, eta_for, resource_ids)
        events = history.events
        last_change = events[-1]["occurred_at"]
        closed_at = last_change if fixture.status in TERMINAL_STATUSES else None

        incident = Incident(
            id=incident_id(fixture.key),
            code=await incidents.next_code(),
            type_id=incident_type.id,
            title=fixture.title,
            description=fixture.description,
            status=fixture.status,
            priority=fixture.priority,
            location=Location(
                id=incident_location_id(fixture.key),
                municipality=fixture.municipality,
                description=fixture.location_description,
                geom=point(*coordinates) if coordinates else None,
                created_at=reported_at,
                updated_at=reported_at,
            ),
            affected_people=fixture.affected_people,
            details=validate_details(incident_type.details_schema_key, fixture.details),
            parent_incident_id=incident_id(fixture.parent_key) if fixture.parent_key else None,
            created_by_id=None,
            is_simulated=True,
            reported_at=reported_at,
            closed_at=closed_at,
            created_at=reported_at,
            updated_at=last_change,
        )
        session.add(incident)
        await session.flush()
        if fixture.parent_key:
            parent_code = await session.scalar(
                select(Incident.code).where(Incident.id == incident_id(fixture.parent_key))
            )
            events[0]["payload"]["parent"] = parent_code
        for index, event in enumerate(events):
            session.add(
                IncidentEvent(
                    id=incident_event_id(fixture.key, index),
                    incident_id=incident.id,
                    actor_user_id=None,
                    is_simulated=True,
                    **event,
                )
            )
        for index, demo in enumerate(history.assignments):
            eta = demo.eta if isinstance(demo.eta, Eta) else None
            session.add(
                ResourceAssignment(
                    id=incident_assignment_id(fixture.key, index),
                    incident_id=incident.id,
                    resource_id=resource_ids[demo.resource_code],
                    assigned_at=demo.assigned_at,
                    arrived_at=demo.arrived_at,
                    released_at=demo.released_at,
                    release_reason=demo.release_reason,
                    eta_minutes=eta.minutes if eta else None,
                    eta_distance_km=Decimal(str(eta.distance_km)) if eta else None,
                    eta_origin=eta.origin if eta else None,
                    is_simulated=True,
                    created_at=demo.assigned_at,
                    updated_at=demo.released_at or demo.arrived_at or demo.assigned_at,
                )
            )
        created.append(f"incident:{fixture.key}")
    await session.flush()
    return created


@dataclass
class _DemoAssignment:
    resource_code: str
    assigned_at: datetime
    eta: Eta | EtaUnavailable
    arrived_at: datetime | None = None
    released_at: datetime | None = None
    release_reason: ReleaseReason | None = None


@dataclass
class _History:
    events: list[dict[str, Any]] = field(default_factory=list)
    assignments: list[_DemoAssignment] = field(default_factory=list)

    def add(self, event_type: IncidentEventType, at: datetime, payload: dict[str, Any]) -> None:
        # Como `EventRecorder`: los eventos del mismo instante, en orden de registro.
        if self.events and at <= self.events[-1]["occurred_at"]:
            at = self.events[-1]["occurred_at"] + timedelta(microseconds=1)
        self.events.append({"event_type": event_type, "occurred_at": at, "payload": payload})

    def active(self, resource_code: str | None = None) -> list[_DemoAssignment]:
        return [
            a
            for a in self.assignments
            if a.released_at is None and resource_code in (None, a.resource_code)
        ]


def _history(
    fixture: DemoIncident,
    type_code: str,
    reported_at: datetime,
    eta_for: Callable[[str], Eta | EtaUnavailable],
    resource_ids: Mapping[str, uuid.UUID],
) -> _History:
    """Eventos y asignaciones del incidente, con las mismas reglas y payloads que
    los servicios (transiciones, cambios automáticos de estado y retirada al
    cerrar). `eta_for(código)` estima la ETA de un recurso hasta el incidente y
    `resource_ids` da el id real de cada recurso por su código."""
    history = _History()
    history.add(
        IncidentEventType.INCIDENT_CREATED,
        reported_at,
        {"status": INITIAL_STATUS, "priority": fixture.priority, "type": type_code, "parent": None},
    )
    status = INITIAL_STATUS

    def set_status(target: IncidentStatus, at: datetime, extra: dict[str, Any]) -> None:
        nonlocal status
        if target != status:
            history.add(
                IncidentEventType.STATUS_CHANGED, at, {"from": status, "to": target, **extra}
            )
            status = target

    def release(assignment: _DemoAssignment, reason: ReleaseReason, at: datetime) -> None:
        assignment.released_at = at
        assignment.release_reason = reason
        history.add(
            IncidentEventType.RESOURCE_RELEASED,
            at,
            {
                "resource": assignment.resource_code,
                "resource_id": str(resource_ids[assignment.resource_code]),
                "reason": reason,
                "reassigned_to": None,
            },
        )

    for step in sorted(fixture.steps, key=lambda s: s.minute):
        at = reported_at + timedelta(minutes=step.minute)
        if step.status is not None:
            if not can_transition(status, step.status):
                raise ValueError(
                    f"Fixture {fixture.key}: transición no válida {status} → {step.status}"
                )
            if step.status in TERMINAL_STATUSES:
                for assignment in history.active():
                    release(assignment, ReleaseReason.INCIDENT_CLOSED, at)
            set_status(step.status, at, {"reason": step.reason} if step.reason else {})
        elif step.note:
            history.add(IncidentEventType.NOTE_ADDED, at, {"text": step.note})
        elif step.assign:
            if history.active(step.assign):
                raise ValueError(f"Fixture {fixture.key}: {step.assign} ya está asignado")
            eta = eta_for(step.assign)
            history.assignments.append(_DemoAssignment(step.assign, at, eta))
            history.add(
                IncidentEventType.RESOURCE_ASSIGNED,
                at,
                {
                    "resource": step.assign,
                    "resource_id": str(resource_ids[step.assign]),
                    "resource_type": RESOURCES_BY_CODE[step.assign].type_code,
                    "eta": None
                    if isinstance(eta, EtaUnavailable)
                    else {
                        "minutes": eta.minutes,
                        "distance_km": eta.distance_km,
                        "origin": eta.origin,
                    },
                    "eta_unavailable": eta if isinstance(eta, EtaUnavailable) else None,
                    "reassigned_from": None,
                },
            )
            set_status(status_after_assignment(status), at, {"cause": StatusChangeCause.ASSIGNMENT})
        elif step.arrive:
            (assignment,) = history.active(step.arrive)
            assignment.arrived_at = at
            history.add(
                IncidentEventType.RESOURCE_ARRIVED,
                at,
                {"resource": step.arrive, "resource_id": str(resource_ids[step.arrive])},
            )
        elif step.release and step.release_reason:
            (assignment,) = history.active(step.release)
            release(assignment, step.release_reason, at)
            if not history.active():
                set_status(
                    status_after_last_release(status), at, {"cause": StatusChangeCause.ASSIGNMENT}
                )
    if status != fixture.status:
        raise ValueError(f"Fixture {fixture.key}: termina en {status}, no en {fixture.status}")
    return history


async def _existing(session: AsyncSession, statement: Any) -> set[Any]:
    """Ids (y, si se piden, códigos) de las filas que ya existen."""
    values: set[Any] = set()
    for row in (await session.execute(statement)).all():
        values.update(row)
    return values


async def _by_code[T: (ResourceType, IncidentType)](
    session: AsyncSession, model: type[T]
) -> dict[str, T]:
    rows: Iterable[T] = await session.scalars(select(model))
    return {row.code: row for row in rows}
