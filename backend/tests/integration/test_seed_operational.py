"""Seed de recursos e incidentes simulados: marcado, coherencia del historial,
idempotencia y respeto a los cambios hechos durante la demo."""

from collections import Counter

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain.enums import (
    IncidentEventType,
    IncidentPriority,
    IncidentStatus,
    ResourceStatus,
)
from app.domain.incident_rules import TERMINAL_STATUSES, reachable_statuses
from app.models import Incident, IncidentEvent, Organization, Resource, ResourceType
from app.services.dashboard import DashboardService
from seeds.fixtures import INCIDENTS, RESOURCES
from seeds.operational import incident_id, resource_id
from seeds.seed import seed

DEMO_PASSWORD = "demo-password-for-tests"


async def _count(session: AsyncSession, model: type[object]) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0


async def _sequence_value(session: AsyncSession) -> int:
    return int(await session.scalar(text("SELECT last_value FROM incident_code_seq")) or 0)


# --- Recursos -------------------------------------------------------------------


async def test_resources_are_created_and_marked_as_simulated(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    resources = (
        await session.scalars(select(Resource).options(joinedload(Resource.organization)))
    ).all()
    assert len(resources) == len(RESOURCES)
    for resource in resources:
        assert resource.id == resource_id(resource.code)
        assert resource.is_simulated
        assert resource.is_active
        assert resource.code.startswith("SIM-")
        assert "(simulado)" in resource.name
        assert resource.organization.is_simulated
    # Hay recursos en los tres estados, con mayoría disponibles.
    statuses = Counter(resource.status for resource in resources)
    assert set(statuses) == set(ResourceStatus)
    assert statuses[ResourceStatus.AVAILABLE] > len(resources) / 2


# --- Incidentes -----------------------------------------------------------------


async def test_incidents_are_created_and_marked_as_simulated(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    incidents = {i.id: i for i in await session.scalars(select(Incident))}
    assert len(incidents) == len(INCIDENTS)
    codes = []
    for fixture in INCIDENTS:
        incident = incidents[incident_id(fixture.key)]
        codes.append(incident.code)
        assert incident.is_simulated
        assert incident.created_by_id is None
        assert "(simulado)" in incident.title
        assert incident.location_description and "simulada" in incident.location_description
        assert incident.status == fixture.status
        assert incident.priority == fixture.priority
        assert (incident.closed_at is not None) == (incident.status in TERMINAL_STATUSES)
    # Códigos de la secuencia, en el orden cronológico de los fixtures.
    assert codes == sorted(codes)
    assert all(code.startswith("INC-") for code in codes)


async def test_incidents_cover_every_reachable_status_and_priority(
    session: AsyncSession,
) -> None:
    await seed(session, DEMO_PASSWORD)

    incidents = (await session.scalars(select(Incident))).all()
    statuses = Counter(incident.status for incident in incidents)
    assert set(statuses) == reachable_statuses()
    assert statuses[IncidentStatus.CLOSED] == 2
    assert statuses[IncidentStatus.CANCELLED] == 1
    assert {incident.priority for incident in incidents} == set(IncidentPriority)


async def test_storm_groups_two_children(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    parent_id = incident_id("storm-central")
    children = (
        await session.scalars(select(Incident).where(Incident.parent_incident_id == parent_id))
    ).all()
    assert {child.id for child in children} == {
        incident_id("storm-flood-gijon"),
        incident_id("storm-landslide-mieres"),
    }
    parent = await session.get(Incident, parent_id)
    assert parent is not None and parent.parent_incident_id is None


async def test_each_history_is_consistent_with_the_incident(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    for incident in await session.scalars(select(Incident)):
        events = (
            await session.scalars(
                select(IncidentEvent)
                .where(IncidentEvent.incident_id == incident.id)
                .order_by(IncidentEvent.occurred_at, IncidentEvent.id)
            )
        ).all()
        created, *rest = events
        assert created.event_type == IncidentEventType.INCIDENT_CREATED
        assert created.occurred_at == incident.reported_at
        assert created.payload["status"] == IncidentStatus.RECEIVED
        assert created.payload["priority"] == incident.priority
        # Instantes distintos: el orden del timeline no depende del id.
        assert len({event.occurred_at for event in events}) == len(events)

        status = IncidentStatus.RECEIVED
        for event in rest:
            if event.event_type == IncidentEventType.STATUS_CHANGED:
                assert event.payload["from"] == status
                status = IncidentStatus(event.payload["to"])
            else:
                assert event.event_type == IncidentEventType.NOTE_ADDED
                assert "(simulado)" in event.payload["text"]
        assert status == incident.status
        # La última actividad del historial es la última modificación.
        assert incident.updated_at == events[-1].occurred_at
        for event in events:
            assert event.is_simulated
            assert event.actor_user_id is None


async def test_child_creation_event_references_the_parent(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    parent = await session.get(Incident, incident_id("storm-central"))
    created = (
        await session.scalars(
            select(IncidentEvent).where(
                IncidentEvent.incident_id == incident_id("storm-flood-gijon"),
                IncidentEvent.event_type == IncidentEventType.INCIDENT_CREATED,
            )
        )
    ).one()
    assert parent is not None
    assert created.payload["parent"] == parent.code


async def test_details_follow_the_type_schema(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    wildfire = await session.get(Incident, incident_id("wildfire-siero"))
    flood = await session.get(Incident, incident_id("storm-flood-gijon"))
    traffic = await session.get(Incident, incident_id("traffic-oviedo"))
    assert wildfire is not None and flood is not None and traffic is not None
    assert wildfire.details == {"affected_hectares": "12.50", "vegetation": "forest"}
    assert flood.details == {"water_level_cm": 60}
    assert traffic.details == {}


async def test_dashboard_reflects_the_seed(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    summary = await DashboardService(session).summary()

    active = [f for f in INCIDENTS if f.status not in TERMINAL_STATUSES]
    assert summary.incidents.active_total == len(active)
    assert summary.incidents.affected_people == sum(f.affected_people or 0 for f in active)
    assert summary.incidents.reported_last_24h == sum(
        1 for f in INCIDENTS if f.reported_minutes_ago < 24 * 60
    )
    assert summary.resources.active_total == len(RESOURCES)
    assert summary.resources.inactive_total == 0


# --- Idempotencia y cambios de la demo ------------------------------------------------


async def test_second_run_creates_nothing_and_does_not_consume_codes(
    session: AsyncSession,
) -> None:
    await seed(session, DEMO_PASSWORD)
    counts = [await _count(session, m) for m in (Resource, Incident, IncidentEvent)]
    sequence = await _sequence_value(session)

    second = await seed(session, DEMO_PASSWORD)

    assert not second.changed
    assert [await _count(session, m) for m in (Resource, Incident, IncidentEvent)] == counts
    assert await _sequence_value(session) == sequence


async def test_demo_changes_are_not_undone(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)
    resource = await session.get(Resource, resource_id("SIM-BOV-03"))
    incident = await session.get(Incident, incident_id("traffic-oviedo"))
    assert resource is not None and incident is not None
    resource.status = ResourceStatus.OUT_OF_SERVICE
    resource.is_active = False
    incident.priority = IncidentPriority.LOW
    incident.status = IncidentStatus.ASSESSING
    await session.commit()

    report = await seed(session, DEMO_PASSWORD)

    assert not report.changed
    await session.refresh(resource)
    await session.refresh(incident)
    assert (resource.status, resource.is_active) == (ResourceStatus.OUT_OF_SERVICE, False)
    assert (incident.priority, incident.status) == (
        IncidentPriority.LOW,
        IncidentStatus.ASSESSING,
    )


async def test_missing_resources_are_recreated_with_the_same_id(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)
    await session.execute(delete(Resource).where(Resource.code == "SIM-SGI-02"))
    await session.commit()

    report = await seed(session, DEMO_PASSWORD)

    assert report.created == ["resource:SIM-SGI-02"]
    assert await session.get(Resource, resource_id("SIM-SGI-02")) is not None


async def test_existing_resource_with_a_seed_code_is_left_alone(session: AsyncSession) -> None:
    # Un recurso creado a mano con un código del seed no rompe el seed.
    organization = Organization(code="manual-org", name="Organización manual")
    session.add(organization)
    resource_type = (
        await session.scalars(select(ResourceType).where(ResourceType.code == "fire_engine"))
    ).one()
    await session.flush()
    session.add(
        Resource(
            code="SIM-BOV-01",
            name="Creado a mano",
            type_id=resource_type.id,
            organization_id=organization.id,
            status=ResourceStatus.AVAILABLE,
            municipality="Oviedo",
        )
    )
    await session.commit()

    report = await seed(session, DEMO_PASSWORD)

    assert "resource:SIM-BOV-01" not in report.created
    manual = (await session.scalars(select(Resource).where(Resource.code == "SIM-BOV-01"))).one()
    assert manual.name == "Creado a mano"
