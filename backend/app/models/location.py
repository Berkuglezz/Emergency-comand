from geoalchemy2 import Geometry, WKBElement, WKTElement
from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, column_property, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

# WGS84: latitud/longitud en grados decimales (CLAUDE.md §2.6).
LOCATION_SRID = 4326


def point(latitude: float, longitude: float) -> WKTElement:
    """Punto WGS84 para `Location.geom`. WKT usa el orden longitud, latitud."""
    return WKTElement(f"POINT({longitude!r} {latitude!r})", srid=LOCATION_SRID)


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Ubicación de un incidente (`incidents.location_id`) o base de un recurso
    (`resources.base_location_id`). Siempre 1:1: una fila nunca se comparte.

    - `municipality` es obligatorio: siempre hay al menos una ubicación textual.
    - `geom` es opcional: NULL significa «sin coordenadas». El tipo
      `geometry(Point, 4326)` ya impide otras geometrías y otros SRID.
    - `latitude`/`longitude` se leen de `geom` (sin columnas duplicadas). Tras
      cambiar `geom` hay que releer la fila para verlas actualizadas.
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
    # Se lee como WKBElement; se escribe con `point()` (WKTElement).
    geom: Mapped[WKBElement | WKTElement | None] = mapped_column(
        Geometry("POINT", srid=LOCATION_SRID, spatial_index=False)
    )

    latitude: Mapped[float | None] = column_property(func.ST_Y(geom))
    longitude: Mapped[float | None] = column_property(func.ST_X(geom))
