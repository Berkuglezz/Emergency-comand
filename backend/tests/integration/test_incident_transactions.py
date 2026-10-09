"""Concurrencia y atomicidad con transacciones reales.

A diferencia del resto de tests de integración, aquí cada sesión hace commits
de verdad (sobre la base de datos de test), porque la concurrencia y la
atomicidad solo se pueden comprobar entre transacciones independientes. Los
datos se eliminan al terminar cada test.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import pytest
from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.session import get_sessionmaker
from app.domain.enums import IncidentEventType, IncidentStatus, RoleCode
from app.domain.exceptions import ConflictError
from app.models import Incident, IncidentEvent, IncidentType, Role, User
from app.repositories.incidents import IncidentRepository
from app.repositories.users import UserRepository
from app.schemas.incidents import (
    IncidentCreate,
    IncidentNoteCreate,
    IncidentStatusChange,
    IncidentUpdate,
)
from app.schemas.locations import LocationInput
from app.services.incidents import IncidentService

# Tiempo que se espera para confirmar que una transacción está bloqueada.
LOCK_WAIT_SECONDS = 0.5


@dataclass(frozen=True)
class Committed:
    user_id: uuid.UUID
    incident_id: uuid.UUID
    type_id: uuid.UUID
    tag: str


async def _actor(user_id: uuid.UUID, session: AsyncSession) -> User:
    user = await UserRepository(session).get_by_id(user_id)
    assert user is not None
    return user


@pytest.fixture
async def committed() -> AsyncIterator[Committed]:
    """Un coordinador y un incidente confirmados en la base de datos de test."""
    maker = get_sessionmaker()
    tag = uuid.uuid4().hex[:10]
    async with maker() as session:
        role = (await session.scalars(select(Role).where(Role.code == RoleCode.COORDINATOR))).one()
        incident_type = (
            await session.scalars(select(IncidentType).where(IncidentType.code == "flood"))
        ).one()
        user = User(
            email=f"tx-{tag}@example.test",
            full_name="Coordinación de prueba",
            password_hash=hash_password("not-used-123"),
            role_id=role.id,
        )
        session.add(user)
        await session.commit()
        user_id, type_id = user.id, incident_type.id
    try:
        async with maker() as session:
            view = await IncidentService(session).create_incident(
                IncidentCreate(
                    type_id=type_id,
                    title=f"tx {tag}",
                    location=LocationInput(municipality="Oviedo"),
                ),
                await _actor(user_id, session),
            )
        yield Committed(user_id, view.incident.id, type_id, tag)
    finally:
        # Se ejecuta aunque falle la preparación: no quedan datos confirmados.
        async with maker() as session, session.begin():
            # Solo en tests: desactiva los triggers en esta transacción para
            # poder limpiar el historial, que es de solo inserción.
            await session.execute(text("SET LOCAL session_replication_role = replica"))
            incidents = select(Incident.id).where(Incident.created_by_id == user_id)
            await session.execute(
                delete(IncidentEvent).where(IncidentEvent.incident_id.in_(incidents))
            )
            await session.execute(delete(Incident).where(Incident.created_by_id == user_id))
            await session.execute(delete(User).where(User.id == user_id))


async def _state(
    incident_id: uuid.UUID,
) -> tuple[IncidentStatus, int, str, list[IncidentEventType]]:
    """Estado confirmado del incidente, leído en una sesión nueva."""
    async with get_sessionmaker()() as session:
        incident = await session.get(Incident, incident_id)
        assert incident is not None
        events = await session.scalars(
            select(IncidentEvent.event_type)
            .where(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.occurred_at, IncidentEvent.id)
        )
        return incident.status, incident.version, incident.title, list(events)


# --- Concurrencia -------------------------------------------------------------------


async def test_concurrent_change_waits_for_the_lock_and_gets_version_conflict(
    committed: Committed,
) -> None:
    maker = get_sessionmaker()

    async def competing_change() -> object:
        async with maker() as session:
            return await IncidentService(session).change_status(
                committed.incident_id,
                IncidentStatusChange(status=IncidentStatus.ASSESSING, version=1),
                await _actor(committed.user_id, session),
            )

    async with maker() as holder:
        # La primera transacción bloquea la fila del incidente…
        await IncidentRepository(holder).get(committed.incident_id, for_update=True)
        competitor = asyncio.create_task(competing_change())
        await asyncio.sleep(LOCK_WAIT_SECONDS)
        # …y la segunda queda esperando en su SELECT … FOR UPDATE.
        assert not competitor.done()

        # La primera completa su cambio (versión 1 → 2) y libera el bloqueo.
        await IncidentService(holder).change_status(
            committed.incident_id,
            IncidentStatusChange(status=IncidentStatus.CANCELLED, version=1),
            await _actor(committed.user_id, holder),
        )

    # La segunda continúa, ve la versión 2 y se rechaza: no gana la última.
    with pytest.raises(ConflictError) as exc:
        await competitor
    assert exc.value.code == "version_conflict"
    assert await _state(committed.incident_id) == (
        IncidentStatus.CANCELLED,
        2,
        f"tx {committed.tag}",
        [IncidentEventType.INCIDENT_CREATED, IncidentEventType.STATUS_CHANGED],
    )


async def test_simultaneous_changes_with_the_same_version_only_one_wins(
    committed: Committed,
) -> None:
    maker = get_sessionmaker()

    async def change(target: IncidentStatus) -> object:
        async with maker() as session:
            return await IncidentService(session).change_status(
                committed.incident_id,
                IncidentStatusChange(status=target, version=1),
                await _actor(committed.user_id, session),
            )

    results = await asyncio.gather(
        change(IncidentStatus.ASSESSING),
        change(IncidentStatus.CANCELLED),
        change(IncidentStatus.ASSESSING),
        return_exceptions=True,
    )

    conflicts = [r for r in results if isinstance(r, ConflictError)]
    successes = [r for r in results if not isinstance(r, BaseException)]
    assert len(successes) == 1
    assert len(conflicts) == 2
    assert all(c.code == "version_conflict" for c in conflicts)
    status, version, _, events = await _state(committed.incident_id)
    assert version == 2
    assert status in {IncidentStatus.ASSESSING, IncidentStatus.CANCELLED}
    assert events == [IncidentEventType.INCIDENT_CREATED, IncidentEventType.STATUS_CHANGED]


# --- Atomicidad: cambio + evento, o nada ----------------------------------------------


@pytest.fixture
def failing_event_insert(committed: Committed, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hace fallar la inserción del historial dentro de la transacción: junto al
    evento real se añade otro que viola una clave ajena (incidente inexistente).

    Depende de `committed` para activarse después de crear los datos de partida.
    """
    original = IncidentRepository.add_event

    def add_event(self: IncidentRepository, event: IncidentEvent) -> None:
        original(self, event)
        original(
            self,
            IncidentEvent(
                incident_id=uuid.uuid4(),
                event_type=IncidentEventType.NOTE_ADDED,
                payload={},
            ),
        )

    monkeypatch.setattr(IncidentRepository, "add_event", add_event)


@pytest.mark.usefixtures("failing_event_insert")
async def test_failed_event_rolls_back_every_kind_of_change(committed: Committed) -> None:
    maker = get_sessionmaker()
    before = await _state(committed.incident_id)

    async def change_status(service: IncidentService, actor: User) -> object:
        return await service.change_status(
            committed.incident_id,
            IncidentStatusChange(status=IncidentStatus.ASSESSING, version=1),
            actor,
        )

    async def update_incident(service: IncidentService, actor: User) -> object:
        return await service.update_incident(
            committed.incident_id, IncidentUpdate(version=1, title="No debe guardarse"), actor
        )

    async def add_note(service: IncidentService, actor: User) -> object:
        return await service.add_note(
            committed.incident_id, IncidentNoteCreate(text="No debe guardarse"), actor
        )

    operations: dict[str, Callable[[IncidentService, User], Awaitable[object]]] = {
        "status": change_status,
        "update": update_incident,
        "note": add_note,
    }
    for name, operation in operations.items():
        async with maker() as session:
            with pytest.raises(IntegrityError):
                await operation(IncidentService(session), await _actor(committed.user_id, session))
        # Ni el cambio del incidente ni ningún evento: todo o nada.
        assert await _state(committed.incident_id) == before, name


@pytest.mark.usefixtures("failing_event_insert")
async def test_failed_event_rolls_back_the_creation(committed: Committed) -> None:
    maker = get_sessionmaker()
    title = f"tx {committed.tag} no creado"

    async with maker() as session:
        with pytest.raises(IntegrityError):
            await IncidentService(session).create_incident(
                IncidentCreate(
                    type_id=committed.type_id,
                    title=title,
                    location=LocationInput(municipality="Gijón"),
                ),
                await _actor(committed.user_id, session),
            )

    async with maker() as session:
        assert await session.scalar(select(func.count()).where(Incident.title == title)) == 0
