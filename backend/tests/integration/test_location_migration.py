"""Migración `incident_locations` (Fase 3.1) con datos: traslado y downgrade.

Usa una base de datos propia (`<db>_migrations_test`), porque recorre las
revisiones arriba y abajo y no puede compartir la base de datos de los demás
tests, que está siempre en `head`.
"""

import asyncio
import os
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings, get_settings
from app.db.session import build_database_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
BEFORE = "48bc2488f9e1"  # incidentes y recursos (Fase 2)
LOCATIONS = "16ed0556ad5c"  # ubicaciones (Fase 3.1)
LOCATION_CHANGED = "22b43ff4025b"  # evento location_changed (Fase 3.2)
RESOURCE_BASES = "3ba873c38add"  # bases de recursos y velocidades (Fase 4.1)
ASSIGNMENTS = "e5df184e14c9"  # asignaciones (Fase 4.3)


def _alembic() -> Config:
    return Config(str(BACKEND_DIR / "alembic.ini"))


async def _admin(settings: Settings, statement: str) -> None:
    engine = create_async_engine(
        build_database_url(settings).set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        async with engine.connect() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


async def _run(settings: Settings, statement: str, **params: Any) -> list[dict[str, Any]]:
    engine = create_async_engine(build_database_url(settings))
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text(statement), params)
            return [dict(row) for row in result.mappings()] if result.returns_rows else []
    finally:
        await engine.dispose()


@pytest.fixture
def migration_db() -> Iterator[Settings]:
    """Base de datos vacía solo para este test; se borra al terminar."""
    previous = os.environ["POSTGRES_DB"]
    name = f"{previous.removesuffix('_test')}_migrations_test"
    assert re.fullmatch(r"[a-z0-9_]+_test", name)
    os.environ["POSTGRES_DB"] = name
    get_settings.cache_clear()
    settings = get_settings()
    asyncio.run(_admin(settings, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    asyncio.run(_admin(settings, f'CREATE DATABASE "{name}"'))
    try:
        yield settings
    finally:
        asyncio.run(_admin(settings, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        os.environ["POSTGRES_DB"] = previous
        get_settings.cache_clear()


def _columns(settings: Settings, table: str) -> set[str]:
    rows = asyncio.run(
        _run(
            settings,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table",
            table=table,
        )
    )
    return {row["column_name"] for row in rows}


def test_locations_migration_moves_data_and_downgrades(migration_db: Settings) -> None:
    settings = migration_db
    command.upgrade(_alembic(), BEFORE)
    for code, municipality, description in [
        ("INC-000001", "Oviedo", "Vía pública (ubicación simulada)"),
        ("INC-000002", "Gijón", None),
    ]:
        asyncio.run(
            _run(
                settings,
                "INSERT INTO incidents (code, type_id, title, status, priority, municipality,"
                " location_description) SELECT :code, id, 'x', 'received', 'medium',"
                " :municipality, :description FROM incident_types WHERE code = 'flood'",
                code=code,
                municipality=municipality,
                description=description,
            )
        )
    before = {
        row["code"]: row
        for row in asyncio.run(_run(settings, "SELECT code, version, updated_at FROM incidents"))
    }

    command.upgrade(_alembic(), LOCATIONS)

    assert {"municipality", "location_description"}.isdisjoint(_columns(settings, "incidents"))
    rows = asyncio.run(
        _run(
            settings,
            "SELECT i.code, i.version, i.updated_at, i.location_id, l.municipality,"
            " l.description, l.geom FROM incidents i JOIN locations l ON l.id = i.location_id"
            " ORDER BY i.code",
        )
    )
    assert [(r["code"], r["municipality"], r["description"], r["geom"]) for r in rows] == [
        ("INC-000001", "Oviedo", "Vía pública (ubicación simulada)", None),
        ("INC-000002", "Gijón", None, None),
    ]
    assert len({row["location_id"] for row in rows}) == 2
    # No es una acción operativa: ni versión ni fecha de modificación cambian.
    for row in rows:
        assert (row["version"], row["updated_at"]) == (
            before[row["code"]]["version"],
            before[row["code"]]["updated_at"],
        )

    asyncio.run(
        _run(
            settings,
            "UPDATE locations SET geom = ST_SetSRID(ST_MakePoint(-5.85, 43.36), 4326),"
            " municipality = 'Siero'"
            " WHERE id = (SELECT location_id FROM incidents WHERE code = 'INC-000001')",
        )
    )

    command.downgrade(_alembic(), BEFORE)

    assert "locations" not in {
        row["table_name"]
        for row in asyncio.run(
            _run(
                settings,
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
            )
        )
    }
    restored = asyncio.run(
        _run(
            settings,
            "SELECT code, municipality, location_description FROM incidents ORDER BY code",
        )
    )
    # El texto vuelve (con los cambios hechos después de migrar); las coordenadas se pierden.
    assert [tuple(row.values()) for row in restored] == [
        ("INC-000001", "Siero", "Vía pública (ubicación simulada)"),
        ("INC-000002", "Gijón", None),
    ]

    # Y se puede volver a migrar.
    command.upgrade(_alembic(), "head")
    assert "location_id" in _columns(settings, "incidents")


def test_location_changed_downgrade_is_refused_when_events_exist(migration_db: Settings) -> None:
    settings = migration_db
    command.upgrade(_alembic(), LOCATION_CHANGED)
    asyncio.run(
        _run(
            settings,
            "WITH loc AS (INSERT INTO locations (municipality) VALUES ('Oviedo') RETURNING id),"
            " inc AS (INSERT INTO incidents (code, type_id, title, status, priority, location_id)"
            " SELECT 'INC-000001', t.id, 'x', 'received', 'medium', loc.id"
            " FROM incident_types t, loc WHERE t.code = 'flood' RETURNING id)"
            " INSERT INTO incident_events (incident_id, event_type)"
            " SELECT id, 'location_changed' FROM inc",
        )
    )

    # El historial es de solo inserción: no se puede volver a un CHECK sin ese tipo.
    with pytest.raises(RuntimeError, match="location_changed"):
        command.downgrade(_alembic(), LOCATIONS)


def test_resource_bases_migration_moves_data_and_downgrades(migration_db: Settings) -> None:
    settings = migration_db
    command.upgrade(_alembic(), LOCATION_CHANGED)
    asyncio.run(
        _run(
            settings,
            "WITH org AS (INSERT INTO organizations (code, name) VALUES ('o', 'O') RETURNING id)"
            " INSERT INTO resources (code, name, type_id, organization_id, status, municipality)"
            " SELECT 'R-01', 'Recurso', t.id, org.id, 'available', 'Gijón'"
            " FROM resource_types t, org WHERE t.code = 'fire_engine'",
        )
    )
    before = asyncio.run(_run(settings, "SELECT version, updated_at FROM resources"))[0]

    command.upgrade(_alembic(), RESOURCE_BASES)

    assert "municipality" not in _columns(settings, "resources")
    row = asyncio.run(
        _run(
            settings,
            "SELECT r.version, r.updated_at, l.municipality, l.geom FROM resources r"
            " JOIN locations l ON l.id = r.base_location_id",
        )
    )[0]
    assert (row["municipality"], row["geom"]) == ("Gijón", None)
    assert (row["version"], row["updated_at"]) == (before["version"], before["updated_at"])
    speeds = asyncio.run(_run(settings, "SELECT code, average_speed_kmh FROM resource_types"))
    assert {s["code"]: s["average_speed_kmh"] for s in speeds}["ambulance_advanced"] == 65

    command.downgrade(_alembic(), LOCATION_CHANGED)

    restored = asyncio.run(_run(settings, "SELECT municipality FROM resources"))
    assert restored == [{"municipality": "Gijón"}]
    # La base huérfana se borra con el downgrade.
    assert asyncio.run(_run(settings, "SELECT count(*) AS n FROM locations")) == [{"n": 0}]
    command.upgrade(_alembic(), "head")


def test_assignments_downgrade_is_refused_when_assignments_exist(migration_db: Settings) -> None:
    settings = migration_db
    command.upgrade(_alembic(), ASSIGNMENTS)
    asyncio.run(
        _run(
            settings,
            "WITH org AS (INSERT INTO organizations (code, name) VALUES ('o', 'O') RETURNING id),"
            " base AS (INSERT INTO locations (municipality) VALUES ('Gijón') RETURNING id),"
            " res AS (INSERT INTO resources (code, name, type_id, organization_id, status,"
            " base_location_id) SELECT 'R-01', 'R', t.id, org.id, 'in_service', base.id"
            " FROM resource_types t, org, base WHERE t.code = 'fire_engine' RETURNING id),"
            " loc AS (INSERT INTO locations (municipality) VALUES ('Oviedo') RETURNING id),"
            " inc AS (INSERT INTO incidents (code, type_id, title, status, priority, location_id)"
            " SELECT 'INC-000001', t.id, 'x', 'resources_assigned', 'medium', loc.id"
            " FROM incident_types t, loc WHERE t.code = 'flood' RETURNING id)"
            " INSERT INTO resource_assignments (incident_id, resource_id, assigned_at)"
            " SELECT inc.id, res.id, now() FROM inc, res",
        )
    )

    # Las asignaciones forman parte del historial: no se pueden deshacer.
    with pytest.raises(RuntimeError, match="asignaciones"):
        command.downgrade(_alembic(), RESOURCE_BASES)
