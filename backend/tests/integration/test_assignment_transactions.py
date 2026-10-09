"""Asignaciones con transacciones reales: concurrencia e índice único parcial.

Como en `test_incident_transactions.py`, aquí las sesiones hacen commit de
verdad y los datos se eliminan al terminar.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.domain.enums import (
    IncidentEventType,
    IncidentStatus,
    ReleaseReason,
    ResourceStatus,
    RoleCode,
)
from app.domain.exceptions import ConflictError, DomainError
from app.main import create_app
from app.models import (
    Incident,
    IncidentEvent,
    IncidentType,
    Location,
    Organization,
    Resource,
    ResourceAssignment,
    ResourceType,
    Role,
    User,
)
from app.repositories.users import UserRepository
from app.schemas.assignments import AssignmentCreate
from app.schemas.incidents import IncidentCreate, IncidentStatusChange
from app.schemas.locations import LocationInput
from app.services.assignments import AssignmentService
from app.services.incidents import IncidentService


@dataclass(frozen=True)
class Scenario:
    user_id: uuid.UUID
    resource_id: uuid.UUID
    incident_ids: tuple[uuid.UUID, uuid.UUID]


@pytest.fixture
async def scenario() -> AsyncIterator[Scenario]:
    """Un coordinador, un recurso disponible y dos incidentes, confirmados."""
    maker = get_sessionmaker()
    tag = uuid.uuid4().hex[:8]
    async with maker() as session:
        role = (await session.scalars(select(Role).where(Role.code == RoleCode.COORDINATOR))).one()
        user = User(
            email=f"asg-{tag}@example.test",
            full_name="Coordinación de prueba",
            password_hash=hash_password("not-used-123"),
            role_id=role.id,
        )
        organization = Organization(code=f"asg-{tag}", name="Organización de prueba")
        session.add_all([user, organization])
        await session.flush()
        resource_type = (
            await session.scalars(select(ResourceType).where(ResourceType.code == "fire_engine"))
        ).one()
        resource = Resource(
            code=f"TX-{tag}".upper(),
            name="Recurso de prueba",
            type_id=resource_type.id,
            organization_id=organization.id,
            status=ResourceStatus.AVAILABLE,
            base=Location(municipality="Oviedo"),
        )
        session.add(resource)
        await session.commit()
        user_id, resource_id, organization_id = user.id, resource.id, organization.id
        base_id = resource.base_location_id
        incident_type = (
            await session.scalars(select(IncidentType).where(IncidentType.code == "flood"))
        ).one()
        type_id = incident_type.id
    incident_ids: list[uuid.UUID] = []
    try:
        for index in range(2):
            async with maker() as session:
                actor = await UserRepository(session).get_by_id(user_id)
                assert actor is not None
                view = await IncidentService(session).create_incident(
                    IncidentCreate(
                        type_id=type_id,
                        title=f"tx {tag} {index}",
                        location=LocationInput(municipality="Oviedo"),
                    ),
                    actor,
                )
                incident_ids.append(view.incident.id)
        yield Scenario(user_id, resource_id, (incident_ids[0], incident_ids[1]))
    finally:
        async with maker() as session, session.begin():
            # Solo en tests: sin triggers para poder limpiar el historial.
            await session.execute(text("SET LOCAL session_replication_role = replica"))
            await session.execute(
                delete(ResourceAssignment).where(ResourceAssignment.resource_id == resource_id)
            )
            incidents = select(Incident.id).where(Incident.created_by_id == user_id)
            await session.execute(
                delete(IncidentEvent).where(IncidentEvent.incident_id.in_(incidents))
            )
            await session.execute(delete(Incident).where(Incident.created_by_id == user_id))
            await session.execute(delete(Resource).where(Resource.id == resource_id))
            await session.execute(delete(Location).where(Location.id == base_id))
            await session.execute(delete(Organization).where(Organization.id == organization_id))
            await session.execute(delete(User).where(User.id == user_id))


async def test_concurrent_assignments_of_one_resource_let_only_one_win(
    scenario: Scenario,
) -> None:
    maker = get_sessionmaker()

    async def assign(incident_id: uuid.UUID) -> str:
        async with maker() as session:
            actor = await UserRepository(session).get_by_id(scenario.user_id)
            assert actor is not None
            try:
                await AssignmentService(session).assign(
                    incident_id,
                    AssignmentCreate(resource_id=scenario.resource_id, version=1),
                    actor,
                )
            except ConflictError as exc:
                return exc.code
            return "assigned"

    results = await asyncio.gather(*(assign(i) for i in scenario.incident_ids))

    assert sorted(results) == ["assigned", "resource_already_assigned"]
    async with maker() as session:
        active = (
            await session.scalars(
                select(ResourceAssignment).where(
                    ResourceAssignment.resource_id == scenario.resource_id,
                    ResourceAssignment.released_at.is_(None),
                )
            )
        ).all()
        assert len(active) == 1


async def test_database_rejects_two_active_assignments(scenario: Scenario) -> None:
    async with get_sessionmaker()() as session:
        for incident_id in scenario.incident_ids:
            session.add(
                ResourceAssignment(
                    incident_id=incident_id,
                    resource_id=scenario.resource_id,
                    assigned_at=text("now()"),
                )
            )
        with pytest.raises(IntegrityError, match="uq_resource_assignments_active_resource"):
            await session.flush()


# --- Cierre y reasignación concurrentes (orden global de bloqueos) -----------------


async def _actor(session: AsyncSession, user_id: uuid.UUID) -> User:
    actor = await UserRepository(session).get_by_id(user_id)
    assert actor is not None
    return actor


async def _assign_to_origin(scenario: Scenario) -> int:
    """Asigna el recurso al primer incidente; devuelve su nueva `version`."""
    origin, _ = scenario.incident_ids
    async with get_sessionmaker()() as session:
        await AssignmentService(session).assign(
            origin,
            AssignmentCreate(resource_id=scenario.resource_id, version=1),
            await _actor(session, scenario.user_id),
        )
    async with get_sessionmaker()() as session:
        incident = await session.get(Incident, origin)
        assert incident is not None
        return incident.version


async def _outcome(operation: Awaitable[object]) -> str:
    try:
        await operation
    except DomainError as exc:
        return exc.code
    return "ok"


async def test_reassign_locks_incidents_before_the_resource(scenario: Scenario) -> None:
    origin, target = scenario.incident_ids
    await _assign_to_origin(scenario)
    maker = get_sessionmaker()

    async def reassign() -> None:
        async with maker() as session:
            await AssignmentService(session).assign(
                target,
                AssignmentCreate(resource_id=scenario.resource_id, version=1, reassign=True),
                await _actor(session, scenario.user_id),
            )

    async with maker() as holder:
        # Otra operación (p. ej. un cierre) tiene bloqueado el incidente de origen…
        await holder.execute(select(Incident).where(Incident.id == origin).with_for_update())
        task = asyncio.create_task(reassign())
        await asyncio.sleep(0.5)
        assert not task.done()
        # …y la reasignación espera sin haber bloqueado todavía el recurso: el
        # cierre puede tomarlo sin esperarla (antes, aquí se cerraba un ciclo).
        async with maker() as other:
            await other.execute(
                select(Resource)
                .where(Resource.id == scenario.resource_id)
                .with_for_update(nowait=True)
            )
            await other.rollback()
        await holder.rollback()
    await task


@pytest.mark.parametrize("round_", range(6))
async def test_concurrent_close_and_reassign_end_consistently(
    scenario: Scenario, round_: int
) -> None:
    origin, target = scenario.incident_ids
    # Alterna qué incidente es el de origen: cubre los dos órdenes de id.
    if round_ % 2:
        origin, target = target, origin
        scenario = Scenario(scenario.user_id, scenario.resource_id, (origin, target))
    origin_version = await _assign_to_origin(scenario)
    maker = get_sessionmaker()

    async def close() -> object:
        async with maker() as session:
            return await IncidentService(session).change_status(
                origin,
                IncidentStatusChange(status=IncidentStatus.CANCELLED, version=origin_version),
                await _actor(session, scenario.user_id),
            )

    async def reassign() -> object:
        async with maker() as session:
            return await AssignmentService(session).assign(
                target,
                AssignmentCreate(resource_id=scenario.resource_id, version=1, reassign=True),
                await _actor(session, scenario.user_id),
            )

    closed, reassigned = await asyncio.gather(_outcome(close()), _outcome(reassign()))

    # Gane quien gane, ninguna termina con un error no controlado. Si la
    # reasignación va primero, cambia la versión del origen y el cierre recibe 409.
    assert (closed, reassigned) in {("ok", "ok"), ("version_conflict", "ok")}
    async with maker() as session:
        assignments = (
            await session.scalars(
                select(ResourceAssignment).where(
                    ResourceAssignment.resource_id == scenario.resource_id
                )
            )
        ).all()
        active = [a for a in assignments if a.released_at is None]
        assert [a.incident_id for a in active] == [target]
        resource = await session.get(Resource, scenario.resource_id)
        assert resource is not None
        assert resource.status == ResourceStatus.IN_SERVICE
        released = [a for a in assignments if a.released_at is not None]
        assert len(released) == 1
        expected = ReleaseReason.INCIDENT_CLOSED if closed == "ok" else ReleaseReason.REASSIGNED
        assert released[0].release_reason == expected
        # Una sola retirada registrada en el historial: sin eventos duplicados.
        releases = (
            await session.scalars(
                select(IncidentEvent).where(
                    IncidentEvent.event_type == IncidentEventType.RESOURCE_RELEASED,
                    IncidentEvent.incident_id.in_(scenario.incident_ids),
                )
            )
        ).all()
        assert len(releases) == 1


async def test_postgres_deadlock_becomes_a_controlled_conflict(scenario: Scenario) -> None:
    """Un interbloqueo real de PostgreSQL llega con `sqlstate` 40P01 y la API lo
    traduce a `409 concurrent_update` (sin reintentos ni 500 genérico)."""
    first, second = scenario.incident_ids
    maker = get_sessionmaker()

    async def lock(a: uuid.UUID, b: uuid.UUID) -> DBAPIError | None:
        async with maker() as session:
            await session.execute(select(Incident).where(Incident.id == a).with_for_update())
            await asyncio.sleep(0.3)
            try:
                await session.execute(select(Incident).where(Incident.id == b).with_for_update())
            except DBAPIError as exc:
                await session.rollback()
                return exc
            await session.rollback()
            return None

    results = await asyncio.gather(lock(first, second), lock(second, first))
    (deadlock,) = [result for result in results if result is not None]
    assert getattr(deadlock.orig, "sqlstate", None) == "40P01"

    app = create_app()

    @app.get("/_test/deadlock")
    async def _raise() -> None:
        raise deadlock

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_test/deadlock")
    assert response.status_code == 409
    assert response.json() == {"detail": "concurrent_update"}
