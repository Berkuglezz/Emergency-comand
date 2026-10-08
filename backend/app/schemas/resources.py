"""Schemas de la API de recursos.

Sin coordenadas, asignaciones ni historial: solo la ficha y el estado actual.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints

from app.domain.enums import ResourceCategory, ResourceStatus
from app.schemas.incidents import Municipality, Version
from app.schemas.organizations import OrganizationSummary


def _normalize_code(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


# Identificador legible del recurso (p. ej. `BOM-OVI-01`). Se guarda en mayúsculas.
# El BeforeValidator va detrás: se ejecuta antes que el patrón y así el
# patrón sigue publicado en OpenAPI (con el orden inverso desaparece).
ResourceCode = Annotated[
    str,
    StringConstraints(pattern=r"^[A-Z0-9][A-Z0-9-]{1,31}$"),
    BeforeValidator(_normalize_code),
]
ResourceName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]

ResourceSort = Literal["code", "status", "-status_changed_at"]


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResourceTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    category: ResourceCategory
    icon: str
    is_active: bool


class ResourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    type: ResourceTypeResponse
    organization: OrganizationSummary
    status: ResourceStatus
    status_changed_at: datetime
    municipality: str
    is_active: bool
    is_simulated: bool
    version: int
    created_at: datetime
    updated_at: datetime


class ResourcePage(BaseModel):
    items: list[ResourceResponse]
    total: int
    limit: int
    offset: int


class ResourceCreate(_Input):
    code: ResourceCode
    name: ResourceName
    type_id: uuid.UUID
    organization_id: uuid.UUID
    municipality: Municipality
    # Si no se indica, el recurso se da de alta disponible.
    status: ResourceStatus | None = None


class ResourceUpdate(_Input):
    """Edición parcial de la ficha. `version` es obligatoria (bloqueo
    optimista). El código no se puede cambiar; el estado tiene su propio
    endpoint y permiso."""

    version: Version
    name: ResourceName | None = None
    type_id: uuid.UUID | None = None
    organization_id: uuid.UUID | None = None
    municipality: Municipality | None = None
    is_active: bool | None = None


class ResourceStatusChange(_Input):
    status: ResourceStatus
    version: Version
