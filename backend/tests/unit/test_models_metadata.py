"""Reglas del esquema que deben cumplirse en todos los modelos."""

from sqlalchemy import DateTime

import app.models  # noqa: F401 — registra todos los modelos
from app.db.base import Base

EXPECTED_TABLES = {
    # Fase 1
    "roles",
    "organizations",
    "users",
    "refresh_tokens",
    # Fase 2
    "incident_types",
    "incidents",
    "incident_events",
    "resource_types",
    "resources",
}


def test_only_expected_tables_are_mapped() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_no_geographic_columns() -> None:
    # PostGIS está habilitado pero no se usa hasta la Fase 3 (CLAUDE.md §2).
    for table in Base.metadata.tables.values():
        for column in table.columns:
            type_name = type(column.type).__name__.lower()
            assert "geometry" not in type_name, column
            assert "geography" not in type_name, column


def test_all_datetimes_are_timezone_aware() -> None:
    # Se almacena siempre en UTC con `timestamptz` (CLAUDE.md §3).
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, DateTime):
                assert column.type.timezone, column
