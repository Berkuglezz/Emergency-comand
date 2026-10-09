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
    ReleaseReason,
    ResourceStatus,
)
from app.domain.eta import EtaOrigin
from app.domain.incident_rules import ACTIVE_STATUSES, TERMINAL_STATUSES, reachable_statuses
from app.models import (
    Incident,
    IncidentEvent,
    Location,
    Organization,
    Resource,
    ResourceAssignment,
    ResourceType,
)
from app.models.location import point
from app.repositories.incidents import IncidentListQuery
from app.services.dashboard import DashboardService
from app.services.incidents import IncidentService
from seeds.fixtures import INCIDENTS, RESOURCES
from seeds.operational import incident_id, incident_location_id, resource_id
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

    incidents = {
        i.id: i
        for i in await session.scalars(select(Incident).options(joinedload(Incident.location)))
    }
    assert len(incidents) == len(INCIDENTS)
    codes = []
    for fixture in INCIDENTS:
        incident = incidents[incident_id(fixture.key)]
        codes.append(incident.code)
        assert incident.is_simulated
        assert incident.created_by_id is None
        assert "(simulado)" in incident.title
        assert incident.location_id == incident_location_id(fixture.key)
        assert incident.location.municipality == fixture.municipality
        assert incident.location.description and "simulada" in incident.location.description
        assert (incident.location.latitude, incident.location.longitude) == (
            fixture.coordinates or (None, None)
        )
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
            elif event.event_type == IncidentEventType.NOTE_ADDED:
                assert "(simulado)" in event.payload["text"]
            else:
                assert event.event_type in {
                    IncidentEventType.RESOURCE_ASSIGNED,
                    IncidentEventType.RESOURCE_ARRIVED,
                    IncidentEventType.RESOURCE_RELEASED,
                }
                assert event.payload["resource"].startswith("SIM-")
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
            base=Location(municipality="Oviedo"),
        )
    )
    await session.commit()

    report = await seed(session, DEMO_PASSWORD)

    assert "resource:SIM-BOV-01" not in report.created
    manual = (await session.scalars(select(Resource).where(Resource.code == "SIM-BOV-01"))).one()
    assert manual.name == "Creado a mano"


async def test_seeded_map_shows_located_and_unlocated_incidents(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    result = await IncidentService(session).map_incidents(IncidentListQuery(), None)

    active = [f for f in INCIDENTS if f.status in ACTIVE_STATUSES]
    assert {incident.id for incident in result.incidents} == {
        incident_id(f.key) for f in active if f.coordinates is not None
    }
    assert result.unlocated_total == sum(1 for f in active if f.coordinates is None)
    assert result.truncated is False


async def test_existing_locations_are_not_touched(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)
    moved = await session.get(Location, incident_location_id("traffic-oviedo"))
    cleared = await session.get(Location, incident_location_id("wildfire-siero"))
    assert moved is not None and cleared is not None
    moved.geom = point(43.4, -5.8)
    cleared.geom = None
    await session.commit()

    report = await seed(session, DEMO_PASSWORD)

    assert not report.changed
    for location in (moved, cleared):
        await session.refresh(location)
    assert (moved.latitude, moved.longitude) == (43.4, -5.8)
    assert cleared.latitude is None


# --- Asignaciones (Fase 4) ------------------------------------------------------


async def test_assignments_are_consistent_with_resources(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    assignments = (await session.scalars(select(ResourceAssignment))).all()
    active = {a.resource_id: a for a in assignments if a.released_at is None}
    for resource in await session.scalars(select(Resource)):
        # En servicio ⇔ con una asignación activa que empezó cuando cambió su estado.
        if resource.status == ResourceStatus.IN_SERVICE:
            assert resource.id in active, resource.code
            assert resource.status_changed_at == active[resource.id].assigned_at
        else:
            assert resource.id not in active, resource.code
    released = [a for a in assignments if a.released_at is not None]
    assert {a.release_reason for a in released} == {
        ReleaseReason.COMPLETED,
        ReleaseReason.INCIDENT_CLOSED,
    }
    for assignment in released:
        released_resource = await session.get(Resource, assignment.resource_id)
        assert released_resource is not None
        assert released_resource.status_changed_at == assignment.released_at
    assert all(a.is_simulated for a in assignments)


async def test_assignments_store_the_estimated_eta(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    assignments = (await session.scalars(select(ResourceAssignment))).all()
    with_eta = [a for a in assignments if a.eta_minutes is not None]
    assert with_eta and all(a.eta_origin == EtaOrigin.BASE for a in with_eta)
    # El aviso sanitario reciente no tiene coordenadas: su asignación no tiene ETA.
    medical = await session.get(Incident, incident_id("medical-gijon"))
    assert medical is not None
    assert medical.status == IncidentStatus.RESOURCES_ASSIGNED
    (unlocated,) = [a for a in assignments if a.incident_id == medical.id]
    assert unlocated.eta_minutes is None
