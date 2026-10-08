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
- Todo lleva `is_simulated = true`. El actor de los eventos es nulo: los
  genera el sistema, no un usuario.
"""

import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import IncidentEventType
from app.domain.geo import validate_coordinates
from app.domain.incident_details import validate_details
from app.domain.incident_rules import INITIAL_STATUS, TERMINAL_STATUSES, can_transition
from app.models import (
    Incident,
    IncidentEvent,
    IncidentType,
    Location,
    Organization,
    Resource,
    ResourceType,
)
from app.models.location import point
from app.repositories.incidents import IncidentRepository
from seeds.fixtures import INCIDENTS, RESOURCES, DemoIncident

# Espacio de nombres de los UUIDv5 del seed (fijo: no cambiarlo nunca).
SEED_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_DNS, "seed.demo.emergency-command.test")


def resource_id(code: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"resource:{code}")


def incident_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"incident:{key}")


def incident_location_id(key: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, f"incident:{key}:location")


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
        session.add(
            Resource(
                id=resource_id(fixture.code),
                code=fixture.code,
                name=fixture.name,
                type_id=types[fixture.type_code].id,
                organization_id=organizations[fixture.organization_code].id,
                status=fixture.status,
                status_changed_at=now - timedelta(minutes=fixture.status_minutes_ago),
                municipality=fixture.municipality,
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
    incidents = IncidentRepository(session)

    created: list[str] = []
    # Los códigos salen de la secuencia en el orden de los fixtures
    # (cronológico); el padre se crea siempre antes que sus hijos.
    for fixture in INCIDENTS:
        if incident_id(fixture.key) in existing:
            continue
        incident_type = types[fixture.type_code]
        reported_at = now - timedelta(minutes=fixture.reported_minutes_ago)
        events = _history(fixture, incident_type.code, reported_at)
        last_change = events[-1]["occurred_at"]
        closed_at = last_change if fixture.status in TERMINAL_STATUSES else None
        coordinates = validate_coordinates(*fixture.coordinates) if fixture.coordinates else None

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
        created.append(f"incident:{fixture.key}")
    await session.flush()
    return created


def _history(fixture: DemoIncident, type_code: str, reported_at: datetime) -> list[dict[str, Any]]:
    """Eventos del incidente, con los mismos payloads que genera el servicio."""
    events: list[dict[str, Any]] = [
        {
            "event_type": IncidentEventType.INCIDENT_CREATED,
            "occurred_at": reported_at,
            "payload": {
                "status": INITIAL_STATUS,
                "priority": fixture.priority,
                "type": type_code,
                "parent": None,
            },
        }
    ]
    status = INITIAL_STATUS
    for step in sorted(fixture.steps, key=lambda s: s.minute):
        occurred_at = reported_at + timedelta(minutes=step.minute)
        if step.status is not None:
            if not can_transition(status, step.status):
                raise ValueError(
                    f"Fixture {fixture.key}: transición no válida {status} → {step.status}"
                )
            payload: dict[str, Any] = {"from": status, "to": step.status}
            if step.reason:
                payload["reason"] = step.reason
            events.append(
                {
                    "event_type": IncidentEventType.STATUS_CHANGED,
                    "occurred_at": occurred_at,
                    "payload": payload,
                }
            )
            status = step.status
        if step.note:
            events.append(
                {
                    "event_type": IncidentEventType.NOTE_ADDED,
                    "occurred_at": occurred_at,
                    "payload": {"text": step.note},
                }
            )
    return events


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
