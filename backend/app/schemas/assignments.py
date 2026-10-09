"""Schemas de la asignación de recursos a incidentes (CLAUDE.md §2.8).

Las escrituras devuelven el detalle del incidente afectado (`IncidentDetail`),
con su nueva `version` y su estado.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import ReleaseReason, ResourceStatus
from app.domain.eta import EtaUnavailable
from app.schemas.incidents import Version
from app.schemas.locations import LocationResponse
from app.schemas.organizations import OrganizationSummary
from app.schemas.resources import EtaResponse, ResourceTypeResponse


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssignedResource(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    status: ResourceStatus
    type: ResourceTypeResponse
    organization: OrganizationSummary
    base: LocationResponse
    is_simulated: bool


class AssignmentResponse(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    resource: AssignedResource
    assigned_at: datetime
    arrived_at: datetime | None
    released_at: datetime | None
    release_reason: ReleaseReason | None
    # Estimación guardada al asignar (no se recalcula).
    eta: EtaResponse | None
    is_simulated: bool


class IncidentCodeRef(BaseModel):
    id: uuid.UUID
    code: str


class AssignmentCandidate(BaseModel):
    """Recurso que se puede asignar, con su ETA estimada desde la base. Es
    ayuda a la decisión: la lista se ordena por ETA, pero nunca se preselecciona
    ni se asigna nada automáticamente."""

    resource: AssignedResource
    eta: EtaResponse | None
    # Motivo si no hay estimación.
    eta_unavailable: EtaUnavailable | None
    # El tipo del recurso está entre los sugeridos por el catálogo del tipo de incidente.
    suggested: bool
    # Si ya está asignado a otro incidente (solo con `include_assigned=true`): asignarlo
    # exige reasignar.
    current_incident: IncidentCodeRef | None


class AssignmentCreate(_Input):
    resource_id: uuid.UUID
    version: Version
    # Si el recurso está asignado a otro incidente, se retira de él y se asigna a este.
    reassign: bool = False


class AssignmentArrival(_Input):
    version: Version


class AssignmentRelease(_Input):
    version: Version
    # Solo `completed`, `not_needed` o `unavailable`: los demás los pone el sistema.
    reason: ReleaseReason
