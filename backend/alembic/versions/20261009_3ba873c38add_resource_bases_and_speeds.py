"""Bases de recursos y velocidades medias (Fase 4.1).

- `resource_types.average_speed_kmh`: velocidad media por tipo para la ETA
  estimada (CLAUDE.md §2.8). Son datos de catálogo, así que los valores se
  cargan aquí, en todos los entornos.
- Cada recurso pasa a tener su base en `locations` (1:1,
  `resources.base_location_id NOT NULL UNIQUE`). Traslado en SQL: el municipio
  actual de cada recurso se copia a una ubicación nueva, sin coordenadas. No
  cambia `version` ni `updated_at` de los recursos.

`downgrade` restaura `resources.municipality` y **pierde las coordenadas** de
las bases.

Revision ID: 3ba873c38add
Revises: 22b43ff4025b
Create Date: 2026-10-09 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3ba873c38add"
down_revision: str | Sequence[str] | None = "22b43ff4025b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Velocidades medias de demostración (km/h), ajustables.
AVERAGE_SPEEDS_KMH = {
    "fire_engine": 50,
    "rescue_vehicle": 55,
    "ambulance_basic": 60,
    "ambulance_advanced": 65,
    "command_vehicle": 60,
    "civil_protection_unit": 50,
    "logistics_support": 45,
}
# Tipo creado después de esta migración sin velocidad explícita.
DEFAULT_SPEED_KMH = 50


def upgrade() -> None:
    # --- Velocidad media por tipo ---------------------------------------------------
    op.add_column("resource_types", sa.Column("average_speed_kmh", sa.Integer(), nullable=True))
    set_speed = sa.text("UPDATE resource_types SET average_speed_kmh = :speed WHERE code = :code")
    for code, speed in AVERAGE_SPEEDS_KMH.items():
        op.execute(set_speed.bindparams(speed=speed, code=code))
    op.execute(
        sa.text(
            "UPDATE resource_types SET average_speed_kmh = :speed WHERE average_speed_kmh IS NULL"
        ).bindparams(speed=DEFAULT_SPEED_KMH)
    )
    op.alter_column("resource_types", "average_speed_kmh", nullable=False)
    op.create_check_constraint(
        op.f("ck_resource_types_average_speed_positive"),
        "resource_types",
        "average_speed_kmh > 0",
    )

    # --- Base de cada recurso -------------------------------------------------------
    op.add_column("resources", sa.Column("base_location_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE resources SET base_location_id = gen_random_uuid()")
    op.execute(
        """
        INSERT INTO locations (id, municipality, description, geom, created_at, updated_at)
        SELECT base_location_id, municipality, NULL, NULL, created_at, updated_at
        FROM resources
        """
    )
    op.alter_column("resources", "base_location_id", nullable=False)
    op.create_unique_constraint(
        op.f("uq_resources_base_location_id"), "resources", ["base_location_id"]
    )
    op.create_foreign_key(
        op.f("fk_resources_base_location_id_locations"),
        "resources",
        "locations",
        ["base_location_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("resources", "municipality")


def downgrade() -> None:
    op.add_column("resources", sa.Column("municipality", sa.String(length=100), nullable=True))
    op.execute(
        """
        UPDATE resources SET municipality = locations.municipality
        FROM locations WHERE locations.id = resources.base_location_id
        """
    )
    op.alter_column("resources", "municipality", nullable=False)
    op.drop_constraint(
        op.f("fk_resources_base_location_id_locations"), "resources", type_="foreignkey"
    )
    op.drop_constraint(op.f("uq_resources_base_location_id"), "resources", type_="unique")
    # Las ubicaciones de las bases quedan huérfanas: se borran.
    op.execute(
        """
        DELETE FROM locations l
        WHERE EXISTS (SELECT 1 FROM resources r WHERE r.base_location_id = l.id)
        """
    )
    op.drop_column("resources", "base_location_id")

    op.drop_constraint(
        op.f("ck_resource_types_average_speed_positive"), "resource_types", type_="check"
    )
    op.drop_column("resource_types", "average_speed_kmh")
