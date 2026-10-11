"""Schemas del mapa operativo (CLAUDE.md §2.12). Geometrías en GeoJSON
(`[longitud, latitud]`, WGS84).

La entrada reutiliza los tipos de coordenadas de `locations.py` (rango, sin NaN
ni infinitos, 6 decimales) y limita el tamaño de las listas: una entrada
desproporcionada se corta aquí. Las reglas de forma (anillo cerrado, vértices,
área de la demo…) son del dominio (`app.domain.map_features`) y la validez
topológica la decide PostGIS. Los 422 nunca repiten la geometría recibida.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.domain.enums import MapFeatureKind, MapFeatureStatus
from app.domain.map_features import MAX_RING_POSITIONS_INPUT
from app.schemas.incidents import EventActor, Version
from app.schemas.locations import Latitude, Longitude


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


Position = tuple[Longitude, Latitude]
# Hasta 10 anillos: así un polígono con huecos recibe su código propio
# (`polygon_holes_not_supported`) en lugar de un error genérico.
_Ring = Annotated[list[Position], Field(max_length=MAX_RING_POSITIONS_INPUT)]

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
RetireReason = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class PolygonInput(_Input):
    type: Literal["Polygon"]
    coordinates: Annotated[list[_Ring], Field(max_length=10)]


class LineStringInput(_Input):
    type: Literal["LineString"]
    coordinates: Annotated[list[Position], Field(max_length=MAX_RING_POSITIONS_INPUT)]


class PointInput(_Input):
    type: Literal["Point"]
    coordinates: Position


GeometryInput = Annotated[PolygonInput | LineStringInput | PointInput, Field(discriminator="type")]


class MapFeatureCreate(_Input):
    """Alta de un elemento. En esta versión la API solo acepta `perimeter`."""

    kind: MapFeatureKind
    geometry: GeometryInput
    label: Label | None = None
    note: Note | None = None


class MapFeatureUpdate(_Input):
    """Edición parcial con `version` obligatoria (bloqueo optimista del
    elemento, D-M7). El tipo no se puede cambiar."""

    version: Version
    geometry: GeometryInput | None = None
    label: Label | None = None
    note: Note | None = None


class MapFeatureRetire(_Input):
    version: Version
    reason: RetireReason


class MapFeatureGeometry(BaseModel):
    type: Literal["Polygon", "LineString", "Point"]
    coordinates: Any


class MapFeatureProperties(BaseModel):
    incident_id: uuid.UUID
    kind: MapFeatureKind
    status: MapFeatureStatus
    label: str | None
    note: str | None
    # Todo lo dibujado es «Dibujado · no validado» (D-M5): no es un dato oficial.
    verification: Literal["unverified"] = "unverified"
    version: int
    created_at: datetime
    created_by: EventActor | None
    updated_at: datetime
    updated_by: EventActor | None
    retired_at: datetime | None
    retired_by: EventActor | None
    retire_reason: str | None
    is_simulated: bool


class MapFeatureResponse(BaseModel):
    """`Feature` GeoJSON con el identificador del elemento."""

    type: Literal["Feature"] = "Feature"
    id: uuid.UUID
    geometry: MapFeatureGeometry
    properties: MapFeatureProperties


class MapFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[MapFeatureResponse]
