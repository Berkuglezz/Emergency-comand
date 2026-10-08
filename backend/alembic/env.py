"""Entorno de migraciones de Alembic (modo async, asyncpg)."""

import asyncio
from logging.config import fileConfig

from alembic import context
from alembic.runtime.environment import NameFilterParentNames, NameFilterType
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401 — registra todos los modelos en Base.metadata
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import build_database_url

config = context.config

if config.config_file_name is not None:
    # Sin desactivar los loggers ya creados (p. ej. al migrar desde los tests).
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Tablas creadas por la extensión PostGIS en el esquema public. No pertenecen a
# los modelos y autogenerate no debe proponer borrarlas.
_EXTENSION_TABLES = frozenset({"spatial_ref_sys"})


def include_name(
    name: str | None, type_: NameFilterType, parent_names: NameFilterParentNames
) -> bool:
    if type_ == "schema":
        # Solo el esquema por defecto; tiger/topology son de PostGIS.
        return name is None
    if type_ == "table":
        return name not in _EXTENSION_TABLES
    return True


def run_migrations_offline() -> None:
    """Genera el SQL sin conectarse (`alembic upgrade head --sql`)."""
    url = build_database_url(get_settings()).render_as_string(hide_password=True)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_name=include_name,
        compare_server_default=True,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # La imagen de PostGIS añade `topology` y `tiger` al search_path de la base
    # de datos; sin esto, autogenerate vería sus tablas como propias.
    connection.exec_driver_sql("SET search_path TO public")
    # El SET abre una transacción implícita; se cierra para que Alembic
    # gestione la suya y haga commit de la migración.
    connection.commit()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_name=include_name,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        build_database_url(get_settings()),
        poolclass=pool.NullPool,
        hide_parameters=True,
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
