import uuid
from datetime import datetime

from geoalchemy2 import Geometry, WKBElement, WKTElement
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, false, func, text
from sqlalchemy.orm import Mapped, column_property, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.domain.enums import MapFeatureKind, MapFeatureStatus
from app.domain.geo import COORDINATE_DECIMALS
from app.models.location import LOCATION_SRID
from app.models.user import User

# Mismo reparto que `GEOMETRY_TYPE_BY_KIND` (app/domain/map_features.py), en SQL.
_KIND_MATCHES_GEOMETRY = (
    "(kind IN ('perimeter', 'affected_area', 'exclusion_zone', 'safe_zone')"
    " AND GeometryType(geom) = 'POLYGON')"
    " OR (kind = 'road_closure' AND GeometryType(geom) = 'LINESTRING')"
    " OR (kind = 'point_of_interest' AND GeometryType(geom) = 'POINT')"
)


class IncidentMapFeature(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Elemento dibujado sobre el mapa de un incidente (CLAUDE.md §2.12).

    - Siempre pertenece a un incidente. Se presenta como «Dibujado · no
      validado» (D-M5): no es un dato oficial.
    - Nunca se borra: retirar fija `status = retired` y `retired_*` (D-M4).
    - `version`: bloqueo optimista propio (D-M7). Editar un elemento no toca la
      fila del incidente ni su `version`.
    - La geometría es `geometry(Geometry, 4326)`. Los CHECK de la tabla exigen
      el tipo que corresponde a cada `kind` y que sea válida (`ST_IsValid`).
    - Cada cambio queda en `incident_events` con la geometría anterior y la
      nueva (D-M3), en la misma transacción. Las geometrías nunca van a logs.
    """

    __tablename__ = "incident_map_features"
    __table_args__ = (
        CheckConstraint(_KIND_MATCHES_GEOMETRY, name="kind_matches_geometry"),
        CheckConstraint("ST_IsValid(geom)", name="geometry_is_valid"),
        CheckConstraint(
            "(status = 'retired') = (retired_at IS NOT NULL)", name="retired_consistency"
        ),
        Index("ix_incident_map_features_geom", "geom", postgresql_using="gist"),
        Index("ix_incident_map_features_incident_status", "incident_id", "status"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="RESTRICT"))
    kind: Mapped[MapFeatureKind] = mapped_column(str_enum(MapFeatureKind, "map_feature_kind"))
    status: Mapped[MapFeatureStatus] = mapped_column(
        str_enum(MapFeatureStatus, "map_feature_status"),
        server_default=text(f"'{MapFeatureStatus.ACTIVE.value}'"),
    )
    # Se lee como WKBElement; se escribe con WKTElement (WKT del dominio).
    geom: Mapped[WKBElement | WKTElement] = mapped_column(
        Geometry("GEOMETRY", srid=LOCATION_SRID, spatial_index=False)
    )
    label: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    retired_at: Mapped[datetime | None]
    retired_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    retire_reason: Mapped[str | None] = mapped_column(String(255))
    is_simulated: Mapped[bool] = mapped_column(server_default=false())
    version: Mapped[int] = mapped_column(server_default=text("1"))

    # lazy="raise": el repositorio carga las relaciones de forma explícita.
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="raise")
    updated_by: Mapped[User | None] = relationship(foreign_keys=[updated_by_id], lazy="raise")
    retired_by: Mapped[User | None] = relationship(foreign_keys=[retired_by_id], lazy="raise")

    # GeoJSON calculado por PostGIS (6 decimales): sin Shapely ni WKB en Python.
    geojson: Mapped[str] = column_property(func.ST_AsGeoJSON(geom, COORDINATE_DECIMALS))

    __mapper_args__ = {"version_id_col": version, "eager_defaults": True}  # noqa: RUF012


def geometry_element(wkt: str) -> WKTElement:
    """Geometría WGS84 para `geom` a partir del WKT normalizado del dominio."""
    return WKTElement(wkt, srid=LOCATION_SRID)
