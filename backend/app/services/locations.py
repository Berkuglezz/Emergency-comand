"""Creación y edición de ubicaciones (`Location`), compartidas por incidentes
y bases de recursos. Cada ubicación pertenece a una sola entidad (1:1)."""

from typing import Any

from app.domain.geo import validate_coordinates
from app.models import Location
from app.models.location import point
from app.schemas.locations import LocationInput


def new_location(data: LocationInput) -> Location:
    coordinates = validate_coordinates(data.latitude, data.longitude)
    return Location(
        municipality=data.municipality,
        description=data.description or None,  # cadena vacía = sin valor
        geom=point(*coordinates) if coordinates else None,
    )


def location_snapshot(location: Location) -> dict[str, Any]:
    return {
        "municipality": location.municipality,
        "description": location.description,
        "latitude": location.latitude,
        "longitude": location.longitude,
    }


def apply_location(location: Location, data: LocationInput) -> dict[str, Any] | None:
    """Sustituye la ubicación completa. Si algo cambia, devuelve los campos
    cambiados con el antes y el después (el payload de `location_changed` en
    los incidentes); si no, `None`.

    Las coordenadas pueden ir al historial, nunca a los logs."""
    coordinates = validate_coordinates(data.latitude, data.longitude)
    before = location_snapshot(location)
    after = {
        "municipality": data.municipality,
        "description": data.description or None,
        "latitude": data.latitude,
        "longitude": data.longitude,
    }
    fields = [name for name in ("municipality", "description") if before[name] != after[name]]
    if (before["latitude"], before["longitude"]) != (after["latitude"], after["longitude"]):
        fields.append("coordinates")
    if not fields:
        return None

    location.municipality = data.municipality
    location.description = data.description or None
    if "coordinates" in fields:
        location.geom = point(*coordinates) if coordinates else None
    return {"fields": sorted(fields), "from": before, "to": after}
