"""Reglas geográficas puras (sin I/O): coordenadas WGS84 y rectángulos.

Convención: la API habla de `latitude`/`longitude`; GeoJSON, WKT y PostGIS
usan el orden `[longitud, latitud]`. Esa conversión solo se hace en el modelo
(`app.models.location`), en el filtro por rectángulo del repositorio y en la
respuesta GeoJSON del mapa.

Las coordenadas son datos sensibles: estas funciones nunca las incluyen en el
código ni en el mensaje de las excepciones.
"""

import math
from dataclasses import dataclass

from app.domain.exceptions import InvalidInputError

LATITUDE_RANGE = (-90.0, 90.0)
LONGITUDE_RANGE = (-180.0, 180.0)
# 6 decimales ≈ 11 cm: más precisión no aporta nada en un incidente.
COORDINATE_DECIMALS = 6


@dataclass(frozen=True, slots=True)
class BoundingBox:
    """Rectángulo en grados WGS84 (no cruza el antimeridiano)."""

    min_longitude: float
    min_latitude: float
    max_longitude: float
    max_latitude: float

    def contains(self, latitude: float, longitude: float) -> bool:
        return (
            self.min_latitude <= latitude <= self.max_latitude
            and self.min_longitude <= longitude <= self.max_longitude
        )


# Área de la demo: Asturias con margen. Es una protección de la demo (detecta,
# sobre todo, latitud y longitud intercambiadas), no geofencing: no dispara nada.
DEMO_AREA = BoundingBox(
    min_longitude=-7.3, min_latitude=42.8, max_longitude=-4.4, max_latitude=43.8
)


def round_coordinate(value: float) -> float:
    return round(value, COORDINATE_DECIMALS)


def validate_coordinates(
    latitude: float | None, longitude: float | None
) -> tuple[float, float] | None:
    """Comprueba un par de coordenadas ya validado en rango por los esquemas.

    Devuelve `(latitud, longitud)` o `None` si no hay coordenadas. Ambas o
    ninguna (`coordinates_incomplete`), y dentro del área de la demo
    (`location_out_of_area`).
    """
    if latitude is None and longitude is None:
        return None
    if latitude is None or longitude is None:
        raise InvalidInputError("coordinates_incomplete")
    if not DEMO_AREA.contains(latitude, longitude):
        raise InvalidInputError("location_out_of_area")
    return latitude, longitude


def parse_bbox(value: str) -> BoundingBox:
    """`minLon,minLat,maxLon,maxLat` (el orden de GeoJSON) → `BoundingBox`.

    Cualquier valor no numérico, no finito, fuera de rango o con el mínimo
    mayor o igual que el máximo → `invalid_bbox`.
    """
    parts = value.split(",")
    if len(parts) != 4:
        raise InvalidInputError("invalid_bbox")
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        raise InvalidInputError("invalid_bbox") from None
    if not all(math.isfinite(number) for number in numbers):
        raise InvalidInputError("invalid_bbox")
    bbox = BoundingBox(*numbers)
    lon_min, lon_max = LONGITUDE_RANGE
    lat_min, lat_max = LATITUDE_RANGE
    if not (
        lon_min <= bbox.min_longitude < bbox.max_longitude <= lon_max
        and lat_min <= bbox.min_latitude < bbox.max_latitude <= lat_max
    ):
        raise InvalidInputError("invalid_bbox")
    return bbox
