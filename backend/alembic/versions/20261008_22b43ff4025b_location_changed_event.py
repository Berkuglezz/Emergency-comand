"""Evento de historial `location_changed` (Fase 3.2).

Amplía el CHECK de `incident_events.event_type`. Sin cambios de datos.

`downgrade` solo es posible si no hay ningún `location_changed`: el historial
es de solo inserción y esas filas no se pueden borrar ni reescribir.

Revision ID: 22b43ff4025b
Revises: 16ed0556ad5c
Create Date: 2026-10-08 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "22b43ff4025b"
down_revision: str | Sequence[str] | None = "16ed0556ad5c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "ck_incident_events_incident_event_type"
BEFORE = (
    "incident_created",
    "status_changed",
    "priority_changed",
    "incident_updated",
    "note_added",
    "parent_changed",
)
AFTER = (*BEFORE, "location_changed")


def _in(values: tuple[str, ...]) -> str:
    return f"event_type IN ({', '.join(repr(value) for value in values)})"


def _replace_check(values: tuple[str, ...]) -> None:
    op.drop_constraint(op.f(CONSTRAINT), "incident_events", type_="check")
    op.create_check_constraint(op.f(CONSTRAINT), "incident_events", _in(values))


def upgrade() -> None:
    _replace_check(AFTER)


def downgrade() -> None:
    remaining = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM incident_events WHERE event_type = 'location_changed'")
    )
    if remaining:
        raise RuntimeError(
            "No se puede deshacer: hay eventos `location_changed` y el historial es de solo"
            " inserción."
        )
    _replace_check(BEFORE)
