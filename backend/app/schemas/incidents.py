"""Schemas de la API de incidentes.

La API devuelve códigos (estado, prioridad, tipo, categoría, riesgos…); el
frontend los traduce.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.domain.enums import (
    IncidentCategory,
    IncidentEventType,
    IncidentPriority,
    IncidentStatus,
)
from app.domain.geo import LATITUDE_RANGE, LONGITUDE_RANGE, round_coordinate

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
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
AffectedPeople = Annotated[int, Field(ge=0, le=100_000)]
Version = Annotated[int, Field(ge=1)]

IncidentSort = Literal["priority", "-reported_at", "reported_at", "-updated_at"]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Tipos de incidente ----------------------------------------------------------


class IncidentTypeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    category: IncidentCategory
    icon: str


class IncidentTypeResponse(IncidentTypeSummary):
    default_priority: IncidentPriority
    suggested_resource_types: list[str]
    common_risks: list[str]
    details_schema_key: str | None
    is_active: bool


# --- Ubicación ----------------------------------------------------------------------


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


# --- Incidentes ------------------------------------------------------------------


class IncidentRef(BaseModel):
    """Referencia breve a otro incidente (padre o hijos)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str
    status: IncidentStatus
    priority: IncidentPriority


class IncidentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str
    status: IncidentStatus
    priority: IncidentPriority
    type: IncidentTypeSummary
    location: LocationResponse
    affected_people: int | None
    parent_incident_id: uuid.UUID | None
    is_simulated: bool
    version: int
    reported_at: datetime
    updated_at: datetime


class IncidentDetail(IncidentSummary):
    description: str | None
    details: dict[str, Any]
    parent: IncidentRef | None
    children: list[IncidentRef]
    closed_at: datetime | None
    created_at: datetime
    # Estados a los que puede pasar ahora mismo, según las reglas del backend.
    # El frontend los usa para ofrecer acciones sin duplicar el flujo.
    allowed_transitions: list[IncidentStatus]


class IncidentPage(BaseModel):
    items: list[IncidentSummary]
    total: int
    limit: int
    offset: int


class IncidentCreate(_Input):
    type_id: uuid.UUID
    title: Title
    description: Description | None = None
    # Si no se indica, se usa la prioridad por defecto del tipo.
    priority: IncidentPriority | None = None
    location: LocationInput
    affected_people: AffectedPeople | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    parent_incident_id: uuid.UUID | None = None


class IncidentUpdate(_Input):
    """Edición parcial: solo se modifican los campos enviados. `version` es
    obligatoria (bloqueo optimista). El tipo no se puede cambiar."""

    version: Version
    title: Title | None = None
    description: Description | None = None
    priority: IncidentPriority | None = None
    location: LocationInput | None = None
    affected_people: AffectedPeople | None = None
    details: dict[str, Any] | None = None
    parent_incident_id: uuid.UUID | None = None


class IncidentStatusChange(_Input):
    status: IncidentStatus
    version: Version
    reason: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class IncidentNoteCreate(_Input):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


# --- Mapa (GeoJSON) ---------------------------------------------------------------------


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    # Orden GeoJSON: [longitud, latitud].
    coordinates: tuple[float, float]


class IncidentMapProperties(BaseModel):
    """Lo mínimo para dibujar y seleccionar; el detalle sale de `GET /incidents/{id}`."""

    id: uuid.UUID
    code: str
    title: str
    status: IncidentStatus
    priority: IncidentPriority
    type_code: str
    type_icon: str
    is_simulated: bool


class IncidentMapFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: PointGeometry
    properties: IncidentMapProperties


class IncidentMapCollection(BaseModel):
    """`FeatureCollection` GeoJSON con dos miembros propios: incidentes que
    cumplen los filtros pero no tienen coordenadas, y si se alcanzó el tope."""

    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[IncidentMapFeature]
    unlocated_total: int
    truncated: bool


# --- Historial ---------------------------------------------------------------------


class EventActor(BaseModel):
    id: uuid.UUID
    full_name: str


class IncidentEventResponse(BaseModel):
    id: uuid.UUID
    event_type: IncidentEventType
    occurred_at: datetime
    actor: EventActor | None
    # Códigos y valores; el frontend compone el texto traducido.
    payload: dict[str, Any]
    is_simulated: bool
