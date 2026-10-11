"""Reglas puras del mapa operativo (CLAUDE.md §2.12): geometrías dibujadas sobre
un incidente. Sin I/O: la validez topológica (autointersecciones) la decide
PostGIS (`ST_IsValid`) en el servicio, y además un CHECK en la tabla.

Convenciones:

- GeoJSON y WKT usan `[longitud, latitud]`, WGS84, 6 decimales (como `geo.py`).
- Las coordenadas son datos sensibles: las excepciones solo llevan un código,
  nunca valores recibidos. Nada de aquí escribe en logs.
- Todo elemento dibujado es «Dibujado · no validado» (D-M5): no hay datos
  oficiales en esta tabla.
"""

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.domain.enums import MapFeatureKind
from app.domain.exceptions import InvalidInputError
from app.domain.geo import (
    DEMO_AREA,
    LATITUDE_RANGE,
    LONGITUDE_RANGE,
    round_coordinate,
)

K = MapFeatureKind

# Geometría que exige cada tipo (también lo impone un CHECK en la tabla).
GEOMETRY_TYPE_BY_KIND: dict[MapFeatureKind, str] = {
    K.PERIMETER: "Polygon",
    K.AFFECTED_AREA: "Polygon",
    K.EXCLUSION_ZONE: "Polygon",
    K.SAFE_ZONE: "Polygon",
    K.ROAD_CLOSURE: "LineString",
    K.POINT_OF_INTEREST: "Point",
}

# Tipos que acepta la API en esta versión (M.1): solo el perímetro. El modelo
# admite el resto para no tener que migrar al habilitarlos.
API_ENABLED_KINDS: frozenset[MapFeatureKind] = frozenset({K.PERIMETER})

# --- Límites explícitos -----------------------------------------------------------

# Vértices distintos de un polígono (sin contar el punto que cierra el anillo).
MAX_POLYGON_VERTICES = 500
# Tope del esquema de entrada (posiciones de un anillo): corta antes del dominio
# las entradas desproporcionadas; entre este y el anterior, `too_many_vertices`.
MAX_RING_POSITIONS_INPUT = 2 * MAX_POLYGON_VERTICES
# GeoJSON normalizado de una geometría, en bytes (500 vértices ocupan ~13 kB).
MAX_GEOMETRY_BYTES = 32_768
# `payload` de un evento del historial: geometría anterior + nueva + metadatos.
MAX_EVENT_PAYLOAD_BYTES = 65_536


@dataclass(frozen=True, slots=True)
class PolygonGeometry:
    """Polígono validado y normalizado: un solo anillo exterior, cerrado,
    redondeado a 6 decimales, sin vértices consecutivos repetidos."""

    ring: tuple[tuple[float, float], ...]

    def as_geojson(self) -> dict[str, Any]:
        return {"type": "Polygon", "coordinates": [[list(position) for position in self.ring]]}

    def as_wkt(self) -> str:
        points = ", ".join(f"{lon!r} {lat!r}" for lon, lat in self.ring)
        return f"POLYGON(({points}))"

    @property
    def vertex_count(self) -> int:
        return len(self.ring) - 1


def ensure_kind_enabled(kind: MapFeatureKind) -> None:
    if kind not in API_ENABLED_KINDS:
        raise InvalidInputError("map_feature_kind_not_enabled")


def validate_polygon(
    kind: MapFeatureKind, geometry_type: str, coordinates: Sequence[Sequence[Sequence[float]]]
) -> PolygonGeometry:
    """Valida y normaliza el polígono de un elemento de tipo área.

    Códigos (sin valores): `geometry_kind_mismatch`, `geometry_empty`,
    `polygon_holes_not_supported`, `too_many_vertices`, `invalid_coordinates`,
    `location_out_of_area`, `ring_not_closed`, `degenerate_polygon`,
    `geometry_too_large`. La autointersección la comprueba PostGIS después.
    """
    if GEOMETRY_TYPE_BY_KIND[kind] != geometry_type or geometry_type != "Polygon":
        raise InvalidInputError("geometry_kind_mismatch")
    if len(coordinates) == 0 or len(coordinates[0]) == 0:
        raise InvalidInputError("geometry_empty")
    if len(coordinates) > 1:
        raise InvalidInputError("polygon_holes_not_supported")
    raw_ring = coordinates[0]
    # Cota antes de recorrer nada: más posiciones de las admisibles.
    if len(raw_ring) > MAX_POLYGON_VERTICES + 1:
        raise InvalidInputError("too_many_vertices")

    ring = [_position(position) for position in raw_ring]
    if ring[0] != ring[-1]:
        raise InvalidInputError("ring_not_closed")

    # Vértices sin el cierre y sin repeticiones consecutivas (tampoco entre el
    # último y el primero): tras redondear, dos clics casi iguales son uno.
    vertices: list[tuple[float, float]] = []
    for position in ring[:-1]:
        if not vertices or vertices[-1] != position:
            vertices.append(position)
    while len(vertices) > 1 and vertices[-1] == vertices[0]:
        vertices.pop()
    if len(vertices) < 3 or len(set(vertices)) < 3 or _collinear(vertices):
        raise InvalidInputError("degenerate_polygon")
    if len(vertices) > MAX_POLYGON_VERTICES:
        raise InvalidInputError("too_many_vertices")

    polygon = PolygonGeometry(ring=(*vertices, vertices[0]))
    if serialized_size(polygon.as_geojson()) > MAX_GEOMETRY_BYTES:
        raise InvalidInputError("geometry_too_large")
    return polygon


def ensure_event_payload_size(payload: Mapping[str, Any]) -> None:
    """El historial no admite entradas desproporcionadas (geometría anterior y
    nueva incluidas)."""
    if serialized_size(payload) > MAX_EVENT_PAYLOAD_BYTES:
        raise InvalidInputError("geometry_too_large")


def serialized_size(value: Mapping[str, Any]) -> int:
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _position(position: Sequence[float]) -> tuple[float, float]:
    """`[lon, lat]` finito, en rango y dentro del área de la demo; redondeado."""
    if len(position) != 2:
        raise InvalidInputError("invalid_coordinates")
    longitude, latitude = position
    if not (math.isfinite(longitude) and math.isfinite(latitude)):
        raise InvalidInputError("invalid_coordinates")
    if not (
        LONGITUDE_RANGE[0] <= longitude <= LONGITUDE_RANGE[1]
        and LATITUDE_RANGE[0] <= latitude <= LATITUDE_RANGE[1]
    ):
        raise InvalidInputError("invalid_coordinates")
    longitude, latitude = round_coordinate(longitude), round_coordinate(latitude)
    if not DEMO_AREA.contains(latitude, longitude):
        raise InvalidInputError("location_out_of_area")
    return longitude, latitude


def _collinear(vertices: Sequence[tuple[float, float]]) -> bool:
    """¿Están todos los vértices en una misma recta? (polígono sin superficie).

    No se usa el área con signo: en una «pajarita» simétrica las dos mitades se
    anulan y daría cero, pero eso es una autointersección y la detecta PostGIS.
    """
    origin = vertices[0]
    direction = next(v for v in vertices if v != origin)
    dx, dy = direction[0] - origin[0], direction[1] - origin[1]
    return all(
        math.isclose(dx * (y - origin[1]), dy * (x - origin[0]), abs_tol=1e-12) for x, y in vertices
    )
