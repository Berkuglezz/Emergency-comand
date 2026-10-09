"""Fixtures comunes.

Los tests nunca usan la base de datos de desarrollo: trabajan sobre
`<POSTGRES_DB>_test`, que se borra, se recrea y se migra desde cero (Alembic)
al inicio de cada ejecución. Cada test corre además dentro de una transacción
que se deshace al terminar.
"""

import asyncio
import os
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Iterator
from pathlib import Path
from typing import Protocol

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, create_async_engine

from app.core.config import Settings, get_settings
from app.core.security import hash_password
from app.db.session import build_database_url, dispose_engine, get_engine, get_session
from app.domain.enums import RoleCode
from app.models import Organization, Role, User

TEST_PASSWORD = "correct-horse-battery-staple"
API = "/api/v1"
Headers = dict[str, str]
BACKEND_DIR = Path(__file__).resolve().parents[1]


def _use_test_database() -> None:
    """Redirige la configuración a la base de datos de test.

    Se ejecuta al importar este conftest, antes de que ningún test cree la
    aplicación o lea la configuración cacheada.
    """
    base_db = Settings().postgres_db.removesuffix("_test")
    os.environ["POSTGRES_DB"] = f"{base_db}_test"
    os.environ["ENVIRONMENT"] = "test"
    get_settings.cache_clear()


_use_test_database()


async def _recreate_database(settings: Settings) -> None:
    name = settings.postgres_db
    # Salvaguarda: nunca se borra una base de datos que no sea de test.
    if not re.fullmatch(r"[a-z0-9_]+_test", name):
        raise RuntimeError(f"Nombre de base de datos de test no válido: {name!r}")
    maintenance = create_async_engine(
        build_database_url(settings).set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with maintenance.connect() as connection:
            await connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            await connection.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        await maintenance.dispose()


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> Iterator[None]:
    """Base de datos de test nueva y migrada desde cero en cada ejecución."""
    asyncio.run(_recreate_database(get_settings()))
    command.upgrade(Config(str(BACKEND_DIR / "alembic.ini")), "head")
    yield


@pytest.fixture(scope="session", autouse=True)
async def _dispose_engine(_test_database: None) -> AsyncIterator[None]:
    # ASGITransport no ejecuta el lifespan: el motor se libera al final de la sesión.
    yield
    await dispose_engine()


@pytest.fixture
async def db_connection() -> AsyncIterator[AsyncConnection]:
    """Conexión con una transacción externa que se deshace al final del test."""
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


def _session_for(connection: AsyncConnection) -> AsyncSession:
    # Los commit de los servicios se convierten en savepoints de la
    # transacción externa: nada persiste después del test.
    return AsyncSession(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


@pytest.fixture
async def session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    async with _session_for(db_connection) as session:
        yield session


@pytest.fixture
def app(db_connection: AsyncConnection) -> FastAPI:
    from app.main import create_app

    app = create_app()

    async def _test_session() -> AsyncIterator[AsyncSession]:
        async with _session_for(db_connection) as session:
            yield session

    app.dependency_overrides[get_session] = _test_session
    return app


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class UserFactory(Protocol):
    def __call__(
        self,
        role: RoleCode,
        *,
        email: str | None = None,
        is_active: bool = True,
        with_organization: bool = False,
    ) -> Awaitable[User]: ...


@pytest.fixture
def make_user(session: AsyncSession) -> UserFactory:
    async def _make_user(
        role: RoleCode,
        *,
        email: str | None = None,
        is_active: bool = True,
        with_organization: bool = False,
    ) -> User:
        role_row = (await session.scalars(select(Role).where(Role.code == role))).one()
        organization = (
            Organization(code=f"test-{role.value}", name=f"Organización {role.value}")
            if with_organization
            else None
        )
        user = User(
            email=email or f"{role.value}@example.test",
            full_name=f"Usuario {role.value}",
            password_hash=hash_password(TEST_PASSWORD),
            role=role_row,
            organization=organization,
            is_active=is_active,
        )
        session.add(user)
        await session.commit()
        return user

    return _make_user


@pytest.fixture
async def headers(client: AsyncClient, make_user: UserFactory) -> dict[RoleCode, Headers]:
    """Cabeceras de autenticación para un usuario de cada rol."""
    result: dict[RoleCode, Headers] = {}
    for role in RoleCode:
        user = await make_user(role)
        response = await client.post(
            f"{API}/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
        )
        client.cookies.clear()
        result[role] = {"Authorization": f"Bearer {response.json()['access_token']}"}
    return result


class MemberHeadersFactory(Protocol):
    def __call__(self, role: RoleCode, organization_id: uuid.UUID | str) -> Awaitable[Headers]: ...


@pytest.fixture
def member_headers(client: AsyncClient, session: AsyncSession) -> MemberHeadersFactory:
    """Cabeceras de un usuario nuevo del rol indicado que pertenece a una
    organización concreta (ámbito organizativo, CLAUDE.md §2.11)."""

    async def _member(role: RoleCode, organization_id: uuid.UUID | str) -> Headers:
        role_row = (await session.scalars(select(Role).where(Role.code == role))).one()
        user = User(
            email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.test",
            full_name=f"Usuario {role.value} de organización",
            password_hash=hash_password(TEST_PASSWORD),
            role=role_row,
            organization_id=uuid.UUID(str(organization_id)),
        )
        session.add(user)
        await session.commit()
        response = await client.post(
            f"{API}/auth/login", json={"email": user.email, "password": TEST_PASSWORD}
        )
        client.cookies.clear()
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _member
