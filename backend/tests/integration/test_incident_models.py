"""Modelos de incidentes y recursos contra el esquema real de la migración."""

import re

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.domain.enums import (
    IncidentEventType,
    IncidentPriority,
    IncidentStatus,
    ResourceStatus,
)
from app.domain.incident_details import DETAILS_SCHEMAS
from app.models import (
    Incident,
    IncidentEvent,
    IncidentType,
    Location,
    Organization,
    Resource,
    ResourceType,
)
from app.repositories.incidents import IncidentRepository


async def _incident_type(session: AsyncSession, code: str = "flood") -> IncidentType:
    return (await session.scalars(select(IncidentType).where(IncidentType.code == code))).one()


async def _new_incident(session: AsyncSession, **overrides: object) -> Incident:
    incident_type = await _incident_type(session)
    values: dict[str, object] = {
        "code": await IncidentRepository(session).next_code(),
        "type_id": incident_type.id,
        "title": "Incidente de prueba",
        "status": IncidentStatus.RECEIVED,
        "priority": IncidentPriority.MEDIUM,
        "location": Location(municipality="Oviedo"),
        **overrides,
    }
    incident = Incident(**values)
    session.add(incident)
    await session.flush()
    return incident


# --- Catálogos (datos de referencia de la migración) ----------------------------


async def test_reference_catalogs_are_created_by_the_migration(session: AsyncSession) -> None:
    incident_types = (await session.scalars(select(IncidentType))).all()
    resource_types = (await session.scalars(select(ResourceType))).all()

    assert len(incident_types) == 10
    assert len(resource_types) == 7


async def test_incident_type_catalog_is_consistent(session: AsyncSession) -> None:
    resource_codes = set(await session.scalars(select(ResourceType.code)))
    for incident_type in await session.scalars(select(IncidentType)):
        # Cada recurso sugerido existe en el catálogo de recursos.
        assert set(incident_type.suggested_resource_types) <= resource_codes, incident_type.code
        # Cada clave de `details` tiene su esquema registrado.
        if incident_type.details_schema_key is not None:
            assert incident_type.details_schema_key in DETAILS_SCHEMAS
        assert incident_type.icon


# --- Incidentes -----------------------------------------------------------------


async def test_incident_codes_come_from_a_single_sequence(session: AsyncSession) -> None:
    repository = IncidentRepository(session)
    first, second = await repository.next_code(), await repository.next_code()

    assert re.fullmatch(r"INC-\d{6}", first)
    assert int(second[4:]) == int(first[4:]) + 1


async def test_incident_defaults(session: AsyncSession) -> None:
    incident = await _new_incident(session)
    await session.refresh(incident)

    assert incident.details == {}
    assert incident.is_simulated is False
    assert incident.version == 1
    assert incident.reported_at.tzinfo is not None
    assert incident.closed_at is None


async def test_version_increments_on_every_update(session: AsyncSession) -> None:
    incident = await _new_incident(session)

    incident.priority = IncidentPriority.HIGH
    await session.flush()
    assert incident.version == 2

    incident.status = IncidentStatus.ASSESSING
    await session.flush()
    assert incident.version == 3


async def test_stale_update_is_rejected(session: AsyncSession) -> None:
    incident = await _new_incident(session)
    # Otro cambio llega antes (p. ej. otro usuario): la versión en BD avanza.
    await session.execute(
        update(Incident)
        .where(Incident.id == incident.id)
        .values(version=Incident.version + 1)
        .execution_options(synchronize_session=False)
    )

    incident.title = "Cambio basado en una versión antigua"
    with pytest.raises(StaleDataError):
        await session.flush()


async def test_incident_cannot_be_its_own_parent(session: AsyncSession) -> None:
    incident = await _new_incident(session)

    with pytest.raises(IntegrityError):
        await session.execute(
            text("UPDATE incidents SET parent_incident_id = id WHERE id = :id"),
            {"id": incident.id},
        )


async def test_affected_people_cannot_be_negative(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await _new_incident(session, affected_people=-1)


# --- Historial (solo inserción) -------------------------------------------------


async def test_incident_events_are_append_only(session: AsyncSession) -> None:
    incident = await _new_incident(session)
    session.add(
        IncidentEvent(
            incident_id=incident.id,
            event_type=IncidentEventType.INCIDENT_CREATED,
            payload={"status": "received"},
        )
    )
    await session.flush()

    for statement in (
        "UPDATE incident_events SET payload = '{}'::jsonb",
        "DELETE FROM incident_events",
        "TRUNCATE incident_events",
    ):
        # El error aborta el savepoint, que se deshace al salir del bloque.
        with pytest.raises(DBAPIError, match="solo inserción"):
            async with session.begin_nested():
                await session.execute(text(statement))


# --- Recursos -------------------------------------------------------------------


async def test_resource_with_type_and_organization(session: AsyncSession) -> None:
    resource_type = (
        await session.scalars(select(ResourceType).where(ResourceType.code == "fire_engine"))
    ).one()
    organization = Organization(code="test-org", name="Organización de prueba")
    session.add(organization)
    await session.flush()
    resource = Resource(
        code="TEST-01",
        name="Recurso de prueba",
        type_id=resource_type.id,
        organization_id=organization.id,
        status=ResourceStatus.AVAILABLE,
        municipality="Gijón",
    )
    session.add(resource)
    await session.flush()
    await session.refresh(resource)

    assert resource.is_active is True
    assert resource.is_simulated is False
    assert resource.version == 1
    assert resource.status_changed_at.tzinfo is not None

    resource.status = ResourceStatus.IN_SERVICE
    await session.flush()
    assert resource.version == 2
