from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# WGS84: latitud/longitud en grados decimales (CLAUDE.md §2.6).
LOCATION_SRID = 4326


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ubicación de un incidente (1:1, `incidents.location_id`).

    - `municipality` es obligatorio: todo incidente tiene al menos una
      ubicación textual.
    - `geom` es opcional: NULL significa «sin coordenadas». El tipo
      `geometry(Point, 4326)` ya impide otras geometrías y otros SRID.
    - Las coordenadas son datos sensibles: nunca se escriben en logs.
    """

    __tablename__ = "locations"
    __table_args__ = (
        # Índice GiST declarado aquí (y no con `spatial_index=True`) para que
        # siga la convención de nombres del resto del esquema.
        Index("ix_locations_geom", "geom", postgresql_using="gist"),
    )

    municipality: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255))
    geom: Mapped[WKBElement | None] = mapped_column(
        Geometry("POINT", srid=LOCATION_SRID, spatial_index=False)
    )
