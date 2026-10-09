"""ETA estimada de un recurso hasta un incidente (CLAUDE.md §2.8). Pura, sin I/O.

    distancia estimada = distancia en línea recta (Haversine) * factor de sinuosidad
    minutos            = ceil(distancia estimada / velocidad media del tipo * 60)

- Cálculo local y determinista: sin APIs externas ni rutas por carretera.
- Factor de sinuosidad global 1.4 (una carretera no es una línea recta;
  Asturias es montañosa). Sin tiempo de activación.
- Siempre es una **estimación**: la interfaz la etiqueta como tal.
- `origin` dice desde dónde se estima: la base del recurso en la Fase 4; la
  última posición conocida cuando exista (Fase 5).
"""

import math
from dataclasses import dataclass
from enum import StrEnum

SINUOSITY_FACTOR = 1.4
# Radio medio de la Tierra (km).
EARTH_RADIUS_KM = 6371.0088

# (latitud, longitud) en grados WGS84.
Point = tuple[float, float]


class EtaOrigin(StrEnum):
    BASE = "base"
    # Reservado para la Fase 5 (posición actual del recurso).
    LAST_POSITION = "last_position"


class EtaUnavailable(StrEnum):
    """Motivo por el que no se puede estimar."""

    INCIDENT_WITHOUT_COORDINATES = "incident_without_coordinates"
    RESOURCE_WITHOUT_POSITION = "resource_without_position"


@dataclass(frozen=True, slots=True)
class Eta:
    minutes: int
    # Distancia estimada por carretera (línea recta * sinuosidad), 1 decimal.
    distance_km: float
    origin: EtaOrigin


def haversine_km(a: Point, b: Point) -> float:
    """Distancia en línea recta sobre la esfera terrestre (km)."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def estimate(
    origin: Point | None,
    destination: Point | None,
    speed_kmh: int,
    origin_kind: EtaOrigin = EtaOrigin.BASE,
) -> Eta | EtaUnavailable:
    """ETA estimada, o el motivo por el que no se puede calcular."""
    if destination is None:
        return EtaUnavailable.INCIDENT_WITHOUT_COORDINATES
    if origin is None:
        return EtaUnavailable.RESOURCE_WITHOUT_POSITION
    if speed_kmh <= 0:  # pragma: no cover — lo impide un CHECK del catálogo
        raise ValueError("la velocidad media debe ser positiva")
    distance = haversine_km(origin, destination) * SINUOSITY_FACTOR
    minutes = math.ceil(distance / speed_kmh * 60)
    return Eta(minutes=minutes, distance_km=round(distance, 1), origin=origin_kind)
