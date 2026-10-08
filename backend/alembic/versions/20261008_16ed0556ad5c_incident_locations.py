"""Ubicaciones de incidentes (Fase 3.1): tabla `locations` con PostGIS.

- `locations`: municipio, descripción y `geom geometry(Point, 4326)` opcional
  (NULL = sin coordenadas), con índice GiST.
- Cada incidente pasa a tener su propia ubicación (1:1):
  `incidents.location_id NOT NULL UNIQUE`.
- Traslado de datos en SQL: `municipality` y `location_description` de cada
  incidente se copian a una ubicación nueva, sin coordenadas. No es una acción
  operativa: no cambia `version`, `updated_at` ni el historial.

`downgrade` restaura las dos columnas de texto y **pierde las coordenadas**.

Revision ID: 16ed0556ad5c
Revises: 48bc2488f9e1
Create Date: 2026-10-08 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = "16ed0556ad5c"
down_revision: str | Sequence[str] | None = "48bc2488f9e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("municipality", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column(
            "geom",
            Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=True,
        ),
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_locations")),
    )
    op.create_index("ix_locations_geom", "locations", ["geom"], postgresql_using="gist")

    # Traslado: una ubicación nueva por incidente, con el id elegido de antemano.
    op.add_column("incidents", sa.Column("location_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE incidents SET location_id = gen_random_uuid()")
    op.execute(
        """
        INSERT INTO locations (id, municipality, description, geom, created_at, updated_at)
        SELECT location_id, municipality, location_description, NULL, created_at, updated_at
        FROM incidents
        """
    )
    op.alter_column("incidents", "location_id", nullable=False)
    op.create_unique_constraint(op.f("uq_incidents_location_id"), "incidents", ["location_id"])
    op.create_foreign_key(
        op.f("fk_incidents_location_id_locations"),
        "incidents",
        "locations",
        ["location_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_column("incidents", "location_description")
    op.drop_column("incidents", "municipality")


def downgrade() -> None:
    op.add_column("incidents", sa.Column("municipality", sa.String(length=100), nullable=True))
    op.add_column(
        "incidents", sa.Column("location_description", sa.String(length=255), nullable=True)
    )
    op.execute(
        """
        UPDATE incidents
        SET municipality = locations.municipality,
            location_description = locations.description
        FROM locations
        WHERE locations.id = incidents.location_id
        """
    )
    op.alter_column("incidents", "municipality", nullable=False)
    op.drop_constraint(op.f("fk_incidents_location_id_locations"), "incidents", type_="foreignkey")
    op.drop_constraint(op.f("uq_incidents_location_id"), "incidents", type_="unique")
    op.drop_column("incidents", "location_id")
    op.drop_index("ix_locations_geom", table_name="locations", postgresql_using="gist")
    op.drop_table("locations")
