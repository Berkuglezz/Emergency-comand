"""Reglas del esquema que deben cumplirse en todos los modelos."""

from geoalchemy2 import Geometry
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
    # Fase 3
    "locations",
    # Fase 4
    "resource_assignments",
    # Mapa operativo (M.1)
    "incident_map_features",
}


def test_only_expected_tables_are_mapped() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_only_expected_geographic_columns() -> None:
    # Fase 3 (CLAUDE.md §2.6): el punto WGS84 de la ubicación. Mapa operativo
    # (M.1, §2.12): la geometría de cada elemento dibujado. Ambas con índice
    # GiST. Nada de `geography`; una columna nueva hace fallar este test.
    geographic = {
        f"{table.name}.{column.name}": column
        for table in Base.metadata.tables.values()
        for column in table.columns
        if any(word in type(column.type).__name__.lower() for word in ("geometry", "geography"))
    }
    assert set(geographic) == {"locations.geom", "incident_map_features.geom"}
    column_type = geographic["locations.geom"].type
    assert isinstance(column_type, Geometry)
    assert (column_type.geometry_type, column_type.srid) == ("POINT", 4326)
    assert geographic["locations.geom"].nullable

    indexes = {str(index.name): index for index in Base.metadata.tables["locations"].indexes}
    assert indexes["ix_locations_geom"].dialect_options["postgresql"]["using"] == "gist"

    feature_geom = geographic["incident_map_features.geom"]
    assert isinstance(feature_geom.type, Geometry)
    assert (feature_geom.type.geometry_type, feature_geom.type.srid) == ("GEOMETRY", 4326)
    assert not feature_geom.nullable
    table = Base.metadata.tables["incident_map_features"]
    feature_indexes = {str(index.name): index for index in table.indexes}
    assert (
        feature_indexes["ix_incident_map_features_geom"].dialect_options["postgresql"]["using"]
        == "gist"
    )


def test_all_datetimes_are_timezone_aware() -> None:
    # Se almacena siempre en UTC con `timestamptz` (CLAUDE.md §3).
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, DateTime):
                assert column.type.timezone, column
