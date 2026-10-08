"""Incidentes y recursos (Fase 2): catálogos, incidentes, historial y recursos.

- Catálogos `incident_types` y `resource_types` con sus datos de referencia
  (no son datos demo: existen en todos los entornos).
- `incidents` con código legible de una secuencia única (`incident_code_seq`)
  y bloqueo optimista (`version`).
- `incident_events`: historial funcional del incidente, solo inserción. Un
  trigger impide UPDATE, DELETE y TRUNCATE.
- `resources` sin coordenadas: la ubicación geográfica llega en la Fase 3.

Ninguna columna, índice ni consulta geográfica.

Revision ID: 48bc2488f9e1
Revises: 2c90a9ee7694
Create Date: 2026-10-07 16:52:00.948343

"""

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "48bc2488f9e1"
down_revision: str | Sequence[str] | None = "2c90a9ee7694"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INCIDENT_CATEGORIES = ("fire", "traffic", "medical", "rescue", "weather", "hazmat", "geological")
PRIORITIES = ("critical", "high", "medium", "low")
INCIDENT_STATUSES = (
    "received",
    "assessing",
    "resources_assigned",
    "in_progress",
    "controlled",
    "closed",
    "cancelled",
)
INCIDENT_EVENT_TYPES = (
    "incident_created",
    "status_changed",
    "priority_changed",
    "incident_updated",
    "note_added",
    "parent_changed",
)
RESOURCE_CATEGORIES = ("fire", "rescue", "medical", "command", "civil_protection", "logistics")
RESOURCE_STATUSES = ("available", "in_service", "out_of_service")

# --- Datos de referencia --------------------------------------------------------
# (code, category, icon)
RESOURCE_TYPES = (
    ("fire_engine", "fire", "Truck"),
    ("rescue_vehicle", "rescue", "Wrench"),
    ("ambulance_basic", "medical", "Ambulance"),
    ("ambulance_advanced", "medical", "Ambulance"),
    ("command_vehicle", "command", "RadioTower"),
    ("civil_protection_unit", "civil_protection", "Shield"),
    ("logistics_support", "logistics", "Package"),
)

# (code, category, icon, default_priority, suggested_resource_types, common_risks, details_key)
INCIDENT_TYPES = (
    (
        "wildfire", "fire", "Flame", "high",
        ["fire_engine", "command_vehicle", "logistics_support"],
        ["smoke_inhalation", "fire_spread", "evacuation_needed"],
        "wildfire",
    ),
    (
        "structure_fire", "fire", "FlameKindling", "high",
        ["fire_engine", "rescue_vehicle", "ambulance_advanced"],
        ["smoke_inhalation", "structural_collapse", "trapped_people"],
        None,
    ),
    (
        "traffic_accident", "traffic", "CarFront", "medium",
        ["rescue_vehicle", "ambulance_basic", "ambulance_advanced"],
        ["trapped_people", "fuel_spill", "secondary_collision"],
        None,
    ),
    (
        "medical_emergency", "medical", "HeartPulse", "high",
        ["ambulance_advanced", "ambulance_basic"],
        ["life_threatening"],
        None,
    ),
    (
        "mountain_rescue", "rescue", "MountainSnow", "high",
        ["rescue_vehicle", "ambulance_basic"],
        ["hypothermia", "difficult_access"],
        None,
    ),
    (
        "water_rescue", "rescue", "LifeBuoy", "high",
        ["rescue_vehicle", "ambulance_advanced"],
        ["drowning", "hypothermia"],
        None,
    ),
    (
        "flood", "weather", "Waves", "medium",
        ["civil_protection_unit", "rescue_vehicle", "logistics_support"],
        ["rising_water", "evacuation_needed", "power_outage"],
        "flood",
    ),
    (
        "severe_weather", "weather", "CloudLightning", "medium",
        ["civil_protection_unit", "logistics_support"],
        ["falling_objects", "power_outage", "road_blocked"],
        None,
    ),
    (
        "hazmat", "hazmat", "Biohazard", "critical",
        ["fire_engine", "command_vehicle", "ambulance_advanced"],
        ["toxic_exposure", "explosion", "evacuation_needed"],
        None,
    ),
    (
        "landslide", "geological", "Mountain", "medium",
        ["civil_protection_unit", "rescue_vehicle"],
        ["road_blocked", "structural_collapse"],
        None,
    ),
)  # fmt: skip

APPEND_ONLY_FUNCTION = """
CREATE FUNCTION incident_events_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'incident_events es de solo inserción (% no permitido)', TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$
"""


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _id_column() -> sa.Column[uuid.UUID]:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _timestamp_column(name: str) -> sa.Column[datetime]:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    # --- Catálogos --------------------------------------------------------------
    resource_types = op.create_table(
        "resource_types",
        _id_column(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("icon", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _timestamp_column("created_at"),
        sa.CheckConstraint(
            _in("category", RESOURCE_CATEGORIES), name=op.f("ck_resource_types_resource_category")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resource_types")),
        sa.UniqueConstraint("code", name=op.f("uq_resource_types_code")),
    )
    incident_types = op.create_table(
        "incident_types",
        _id_column(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("icon", sa.String(length=64), nullable=False),
        sa.Column("default_priority", sa.String(length=32), nullable=False),
        sa.Column(
            "suggested_resource_types",
            postgresql.ARRAY(sa.String(length=64)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column(
            "common_risks",
            postgresql.ARRAY(sa.String(length=64)),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("details_schema_key", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        _timestamp_column("created_at"),
        sa.CheckConstraint(
            _in("category", INCIDENT_CATEGORIES), name=op.f("ck_incident_types_incident_category")
        ),
        sa.CheckConstraint(
            _in("default_priority", PRIORITIES), name=op.f("ck_incident_types_incident_priority")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_types")),
        sa.UniqueConstraint("code", name=op.f("uq_incident_types_code")),
    )

    # --- Incidentes -------------------------------------------------------------
    op.execute("CREATE SEQUENCE incident_code_seq")
    op.create_table(
        "incidents",
        _id_column(),
        sa.Column("code", sa.String(length=20), nullable=False),
        sa.Column("type_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("municipality", sa.String(length=100), nullable=False),
        sa.Column("location_description", sa.String(length=255), nullable=True),
        sa.Column("affected_people", sa.Integer(), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("parent_incident_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _timestamp_column("reported_at"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.CheckConstraint(
            "affected_people IS NULL OR affected_people >= 0",
            name=op.f("ck_incidents_affected_people_non_negative"),
        ),
        sa.CheckConstraint(
            "parent_incident_id IS NULL OR parent_incident_id <> id",
            name=op.f("ck_incidents_not_own_parent"),
        ),
        sa.CheckConstraint(
            _in("status", INCIDENT_STATUSES), name=op.f("ck_incidents_incident_status")
        ),
        sa.CheckConstraint(
            _in("priority", PRIORITIES), name=op.f("ck_incidents_incident_priority")
        ),
        sa.ForeignKeyConstraint(
            ["type_id"],
            ["incident_types.id"],
            name=op.f("fk_incidents_type_id_incident_types"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_incident_id"],
            ["incidents.id"],
            name=op.f("fk_incidents_parent_incident_id_incidents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_incidents_created_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
        sa.UniqueConstraint("code", name=op.f("uq_incidents_code")),
    )
    op.create_index(op.f("ix_incidents_type_id"), "incidents", ["type_id"])
    op.create_index(op.f("ix_incidents_status"), "incidents", ["status"])
    op.create_index(op.f("ix_incidents_priority"), "incidents", ["priority"])
    op.create_index(op.f("ix_incidents_parent_incident_id"), "incidents", ["parent_incident_id"])
    op.create_index(op.f("ix_incidents_reported_at"), "incidents", ["reported_at"])
    op.create_index(
        "ix_incidents_active_reported_at",
        "incidents",
        ["reported_at"],
        postgresql_where=sa.text("status NOT IN ('closed', 'cancelled')"),
    )

    # --- Historial del incidente (solo inserción) -------------------------------
    op.create_table(
        "incident_events",
        _id_column(),
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        _timestamp_column("occurred_at"),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.CheckConstraint(
            _in("event_type", INCIDENT_EVENT_TYPES),
            name=op.f("ck_incident_events_incident_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_incident_events_incident_id_incidents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_incident_events_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incident_events")),
    )
    op.create_index(
        "ix_incident_events_incident_id_occurred_at",
        "incident_events",
        ["incident_id", "occurred_at"],
    )
    # Solo inserción también a nivel de base de datos.
    op.execute(APPEND_ONLY_FUNCTION)
    op.execute(
        "CREATE TRIGGER incident_events_no_update_delete "
        "BEFORE UPDATE OR DELETE ON incident_events "
        "FOR EACH ROW EXECUTE FUNCTION incident_events_append_only()"
    )
    op.execute(
        "CREATE TRIGGER incident_events_no_truncate "
        "BEFORE TRUNCATE ON incident_events "
        "FOR EACH STATEMENT EXECUTE FUNCTION incident_events_append_only()"
    )

    # --- Recursos ---------------------------------------------------------------
    op.create_table(
        "resources",
        _id_column(),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("type_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        _timestamp_column("status_changed_at"),
        sa.Column("municipality", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.CheckConstraint(
            _in("status", RESOURCE_STATUSES), name=op.f("ck_resources_resource_status")
        ),
        sa.ForeignKeyConstraint(
            ["type_id"],
            ["resource_types.id"],
            name=op.f("fk_resources_type_id_resource_types"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_resources_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resources")),
        sa.UniqueConstraint("code", name=op.f("uq_resources_code")),
    )
    op.create_index(op.f("ix_resources_type_id"), "resources", ["type_id"])
    op.create_index(op.f("ix_resources_organization_id"), "resources", ["organization_id"])
    op.create_index(op.f("ix_resources_status"), "resources", ["status"])

    # --- Datos de referencia ----------------------------------------------------
    op.bulk_insert(
        resource_types,
        [
            {"code": code, "category": category, "icon": icon}
            for code, category, icon in RESOURCE_TYPES
        ],
    )
    op.bulk_insert(
        incident_types,
        [
            {
                "code": code,
                "category": category,
                "icon": icon,
                "default_priority": priority,
                "suggested_resource_types": suggested,
                "common_risks": risks,
                "details_schema_key": details_key,
            }
            for code, category, icon, priority, suggested, risks, details_key in INCIDENT_TYPES
        ],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_resources_status"), table_name="resources")
    op.drop_index(op.f("ix_resources_organization_id"), table_name="resources")
    op.drop_index(op.f("ix_resources_type_id"), table_name="resources")
    op.drop_table("resources")
    op.execute("DROP TRIGGER incident_events_no_truncate ON incident_events")
    op.execute("DROP TRIGGER incident_events_no_update_delete ON incident_events")
    op.execute("DROP FUNCTION incident_events_append_only()")
    op.drop_index("ix_incident_events_incident_id_occurred_at", table_name="incident_events")
    op.drop_table("incident_events")
    op.drop_index("ix_incidents_active_reported_at", table_name="incidents")
    op.drop_index(op.f("ix_incidents_reported_at"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_parent_incident_id"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_priority"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_status"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_type_id"), table_name="incidents")
    op.drop_table("incidents")
    op.execute("DROP SEQUENCE incident_code_seq")
    op.drop_table("incident_types")
    op.drop_table("resource_types")
