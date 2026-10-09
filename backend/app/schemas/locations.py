"""Schemas de ubicación compartidos (incidentes y bases de recursos).

Coordenadas WGS84 en grados decimales. Las reglas que dependen del dominio
(ambas o ninguna, área de la demo) las aplica el servicio con
`app.domain.geo.validate_coordinates`.
"""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.domain.geo import LATITUDE_RANGE, LONGITUDE_RANGE, round_coordinate


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


Municipality = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
LocationDescription = Annotated[str, StringConstraints(strip_whitespace=True, max_length=255)]
# Grados decimales WGS84; sin NaN ni infinitos, redondeados a 6 decimales.
Latitude = Annotated[
    float,
    Field(ge=LATITUDE_RANGE[0], le=LATITUDE_RANGE[1], allow_inf_nan=False),
    AfterValidator(round_coordinate),
]
Longitude = Annotated[
    float,
    Field(ge=LONGITUDE_RANGE[0], le=LONGITUDE_RANGE[1], allow_inf_nan=False),
    AfterValidator(round_coordinate),
]


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    municipality: str
    description: str | None
    # Ambas nulas = sin coordenadas.
    latitude: float | None
    longitude: float | None


class LocationInput(_Input):
    """Ubicación completa: en una edición sustituye a la anterior (omitir las
    coordenadas las borra). Coordenadas: ambas o ninguna, y dentro del área de
    la demo (lo comprueba el servicio: `coordinates_incomplete`,
    `location_out_of_area`)."""

    municipality: Municipality
    description: LocationDescription | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
