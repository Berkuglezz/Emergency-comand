"""Motor y sesiones async de SQLAlchemy (asyncpg)."""

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings


def build_database_url(settings: Settings) -> URL:
    # URL.create escapa usuario y contraseña; no se concatena a mano.
    return URL.create(
        drivername="postgresql+asyncpg",
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_db,
    )


@lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(
        build_database_url(settings),
        echo=settings.db_echo,
        # Los parámetros de las consultas (p. ej. hashes) nunca aparecen en logs
        # ni en los mensajes de excepción.
        hide_parameters=True,
        pool_pre_ping=True,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Una sesión por petición. Los servicios deciden cuándo hacer commit."""
    async with get_sessionmaker()() as session:
        yield session


async def dispose_engine() -> None:
    if get_engine.cache_info().currsize:
        await get_engine().dispose()
        get_engine.cache_clear()
        get_sessionmaker.cache_clear()
