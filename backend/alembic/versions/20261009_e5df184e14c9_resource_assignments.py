"""Asignación de recursos a incidentes (Fase 4.3).

- `resource_assignments`: activa mientras `released_at` es nulo; nunca se
  borra. Índice único parcial: un recurso solo tiene una asignación activa.
  `eta_*` guarda la estimación en el momento de asignar.
- Amplía el CHECK de `incident_events.event_type` con `resource_assigned`,
  `resource_arrived` y `resource_released`.

`downgrade` solo es posible si no hay asignaciones ni eventos de asignación:
el historial es de solo inserción y esas filas no se pueden reescribir.

Revision ID: e5df184e14c9
Revises: 3ba873c38add
Create Date: 2026-10-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5df184e14c9"
down_revision: str | Sequence[str] | None = "3ba873c38add"
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
)
EVENTS_AFTER = (*EVENTS_BEFORE, "resource_assigned", "resource_arrived", "resource_released")
RELEASE_REASONS = ("completed", "not_needed", "unavailable", "reassigned", "incident_closed")
ETA_ORIGINS = ("base", "last_position")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _replace_event_check(values: tuple[str, ...]) -> None:
    op.drop_constraint(op.f(EVENT_CHECK), "incident_events", type_="check")
    op.create_check_constraint(op.f(EVENT_CHECK), "incident_events", _in("event_type", values))


def upgrade() -> None:
    op.create_table(
        "resource_assignments",
        sa.Column("incident_id", sa.Uuid(), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("assigned_by_id", sa.Uuid(), nullable=True),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_by_id", sa.Uuid(), nullable=True),
        sa.Column("release_reason", sa.String(length=32), nullable=True),
        sa.Column("eta_minutes", sa.Integer(), nullable=True),
        sa.Column("eta_distance_km", sa.Numeric(precision=6, scale=1), nullable=True),
        sa.Column("eta_origin", sa.String(length=32), nullable=True),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            _in("release_reason", RELEASE_REASONS),
            name=op.f("ck_resource_assignments_release_reason"),
        ),
        sa.CheckConstraint(
            _in("eta_origin", ETA_ORIGINS), name=op.f("ck_resource_assignments_eta_origin")
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_resource_assignments_incident_id_incidents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resource_id"],
            ["resources.id"],
            name=op.f("fk_resource_assignments_resource_id_resources"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_by_id"],
            ["users.id"],
            name=op.f("fk_resource_assignments_assigned_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["released_by_id"],
            ["users.id"],
            name=op.f("fk_resource_assignments_released_by_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_resource_assignments")),
    )
    op.create_index(
        "uq_resource_assignments_active_resource",
        "resource_assignments",
        ["resource_id"],
        unique=True,
        postgresql_where=sa.text("released_at IS NULL"),
    )
    op.create_index(
        "ix_resource_assignments_incident_released",
        "resource_assignments",
        ["incident_id", "released_at"],
    )
    op.create_index(
        "ix_resource_assignments_resource_assigned",
        "resource_assignments",
        ["resource_id", "assigned_at"],
    )
    _replace_event_check(EVENTS_AFTER)


def downgrade() -> None:
    bind = op.get_bind()
    events = bind.scalar(
        sa.text(
            "SELECT count(*) FROM incident_events WHERE event_type IN"
            " ('resource_assigned', 'resource_arrived', 'resource_released')"
        )
    )
    assignments = bind.scalar(sa.text("SELECT count(*) FROM resource_assignments"))
    if events or assignments:
        raise RuntimeError(
            "No se puede deshacer: hay asignaciones o eventos de asignación y el historial"
            " es de solo inserción."
        )
    _replace_event_check(EVENTS_BEFORE)
    op.drop_index("ix_resource_assignments_resource_assigned", table_name="resource_assignments")
    op.drop_index("ix_resource_assignments_incident_released", table_name="resource_assignments")
    op.drop_index(
        "uq_resource_assignments_active_resource",
        table_name="resource_assignments",
        postgresql_where=sa.text("released_at IS NULL"),
    )
    op.drop_table("resource_assignments")
