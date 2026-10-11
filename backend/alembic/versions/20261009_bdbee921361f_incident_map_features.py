"""Mapa operativo: geometrías dibujadas sobre un incidente (M.1).

- `incident_map_features`: tipo (`kind`), geometría `geometry(Geometry, 4326)`,
  etiqueta, nota, estado (`active` / `retired`), autoría, retirada y
  `version` propia. Nunca se borra. CHECK: el tipo de geometría corresponde al
  `kind`, la geometría es válida (`ST_IsValid`) y el estado es coherente con
  `retired_at`. Índice GiST sobre la geometría.
- Amplía el CHECK de `incident_events.event_type` con `map_feature_added`,
  `map_feature_updated` y `map_feature_retired`.

`downgrade` solo es posible si no hay geometrías ni eventos de geometría: se
niega en lugar de perder datos o reescribir el historial (solo inserción).

Revision ID: bdbee921361f
Revises: e5df184e14c9
Create Date: 2026-10-09 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "bdbee921361f"
down_revision: str | Sequence[str] | None = "e5df184e14c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EVENT_CHECK = "ck_incident_events_incident_event_type"
EVENTS_BEFORE = (
    "incident_created",
    "status_changed",
    "priority_changed",
    "incident_updated",
    "note_added",
    "parent_changed",
    "location_changed",
    "resource_assigned",
    "resource_arrived",
    "resource_released",
)
MAP_EVENTS = ("map_feature_added", "map_feature_updated", "map_feature_retired")
EVENTS_AFTER = (*EVENTS_BEFORE, *MAP_EVENTS)
KINDS = (
    "perimeter",
    "affected_area",
    "road_closure",
    "exclusion_zone",
    "safe_zone",
    "point_of_interest",
)
STATUSES = ("active", "retired")
KIND_MATCHES_GEOMETRY = (
    "(kind IN ('perimeter', 'affected_area', 'exclusion_zone', 'safe_zone')"
    " AND GeometryType(geom) = 'POLYGON')"
    " OR (kind = 'road_closure' AND GeometryType(geom) = 'LINESTRING')"
    " OR (kind = 'point_of_interest' AND GeometryType(geom) = 'POINT')"
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _replace_event_check(values: tuple[str, ...]) -> None:
    op.drop_constraint(op.f(EVENT_CHECK), "incident_events", type_="check")
    op.create_check_constraint(op.f(EVENT_CHECK), "incident_events", _in("event_type", values))


def upgrade() -> None:
    op.create_table(
        "incident_map_features",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column(
            "geom",
            Geometry(geometry_type="GEOMETRY", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_id", sa.Uuid(), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_by_id", sa.Uuid(), nullable=True),
        sa.Column("retire_reason", sa.String(length=255), nullable=True),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            _in("kind", KINDS), name=op.f("ck_incident_map_features_map_feature_kind")
        ),
        sa.CheckConstraint(
            _in("status", STATUSES), name=op.f("ck_incident_map_features_map_feature_status")
        ),
        sa.CheckConstraint(
            KIND_MATCHES_GEOMETRY, name=op.f("ck_incident_map_features_kind_matches_geometry")
        ),
        sa.CheckConstraint(
            "ST_IsValid(geom)", name=op.f("ck_incident_map_features_geometry_is_valid")
        ),
        sa.CheckConstraint(
            "(status = 'retired') = (retired_at IS NOT NULL)",
            name=op.f("ck_incident_map_features_retired_consistency"),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_map_features_incident_id_incidents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_incident_map_features_created_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_id"],
            ["users.id"],
            name=op.f("fk_incident_map_features_updated_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["retired_by_id"],
            ["users.id"],
            name=op.f("fk_incident_map_features_retired_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_map_features")),
    )
    op.create_index(
        "ix_incident_map_features_geom",
        "incident_map_features",
        ["geom"],
        postgresql_using="gist",
    )
    op.create_index(
        "ix_incident_map_features_incident_status",
        "incident_map_features",
        ["incident_id", "status"],
    )
    _replace_event_check(EVENTS_AFTER)


def downgrade() -> None:
    bind = op.get_bind()
    events = bind.scalar(
        sa.text(
            "SELECT count(*) FROM incident_events WHERE event_type IN"
            " ('map_feature_added', 'map_feature_updated', 'map_feature_retired')"
        )
    )
    features = bind.scalar(sa.text("SELECT count(*) FROM incident_map_features"))
    if events or features:
        raise RuntimeError(
            "No se puede deshacer: hay geometrías del mapa operativo o eventos de geometría,"
            " y el historial es de solo inserción. Ningún dato se ha modificado."
        )
    _replace_event_check(EVENTS_BEFORE)
    op.drop_index("ix_incident_map_features_incident_status", table_name="incident_map_features")
    op.drop_index(
        "ix_incident_map_features_geom",
        table_name="incident_map_features",
        postgresql_using="gist",
    )
    op.drop_table("incident_map_features")
