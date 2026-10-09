"""Lógica de negocio de recursos.

Se guarda el estado actual y `status_changed_at` (sin historial de estados).
La base es una `Location` 1:1. Los recursos no se borran; se desactivan con
`is_active`.
"""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import ConflictError, InvalidInputError, NotFoundError
from app.domain.resource_rules import INITIAL_STATUS, can_change_status
from app.models import Organization, Resource, ResourceAssignment, ResourceType
from app.repositories.assignments import AssignmentRepository
from app.repositories.organizations import OrganizationRepository
from app.repositories.resources import ResourceListQuery, ResourceRepository
from app.schemas.resources import ResourceCreate, ResourceStatusChange, ResourceUpdate
from app.services.locations import apply_location, new_location
from app.services.transactions import commit_or_conflict

# Campos de la ficha que no admiten `null` en una edición parcial.
_NOT_NULLABLE = frozenset({"name", "type_id", "organization_id", "base", "is_active"})


class ResourceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._resources = ResourceRepository(session)
        self._organizations = OrganizationRepository(session)
        self._assignments = AssignmentRepository(session)

    # --- Consultas --------------------------------------------------------------

    async def list_types(self) -> Sequence[ResourceType]:
        return await self._resources.list_types()

    async def list_resources(self, query: ResourceListQuery) -> tuple[Sequence[Resource], int]:
        return await self._resources.list(query)

    async def current_assignments(
        self, resources: Sequence[Resource]
    ) -> dict[uuid.UUID, tuple[ResourceAssignment, str]]:
        """Asignación activa de cada recurso, con el código de su incidente."""
        return await self._assignments.current_for_resources(r.id for r in resources)

    async def get_resource(self, resource_id: uuid.UUID) -> Resource:
        resource = await self._resources.get(resource_id)
        if resource is None:
            raise NotFoundError("resource_not_found")
        return resource

    # --- Escritura ----------------------------------------------------------------

    async def create_resource(self, data: ResourceCreate) -> Resource:
        if await self._resources.code_exists(data.code):
            raise ConflictError("resource_code_taken")
        resource_type = await self._active_type(data.type_id)
        organization = await self._active_organization(data.organization_id)

        resource = Resource(
            code=data.code,
            name=data.name,
            type_id=resource_type.id,
            organization_id=organization.id,
            status=data.status or INITIAL_STATUS,
            status_changed_at=datetime.now(UTC),
            base=new_location(data.base),
            is_simulated=False,
        )
        self._resources.add(resource)
        await commit_or_conflict(self._session)
        return await self.get_resource(resource.id)

    async def update_resource(self, resource_id: uuid.UUID, data: ResourceUpdate) -> Resource:
        """Edición parcial de la ficha. Si ningún valor cambia de verdad, no se
        escribe nada y `version` no se incrementa."""
        resource = await self._load_for_change(resource_id, data.version)

        sent = data.model_fields_set - {"version"}
        if any(getattr(data, name) is None for name in sent & _NOT_NULLABLE):
            raise InvalidInputError("field_not_nullable")

        # Solo se valida el tipo o la organización si de verdad cambian: un
        # recurso existente puede seguir en un tipo u organización ya inactivos.
        # Todas las consultas van antes de modificar nada: así el autoflush no
        # emite un UPDATE intermedio y `version` sube una sola vez.
        if data.type_id is not None and data.type_id != resource.type_id:
            await self._active_type(data.type_id)
        if data.organization_id is not None and data.organization_id != resource.organization_id:
            await self._active_organization(data.organization_id)
        # Un recurso asignado no se desactiva: antes se retira desde el incidente.
        if data.is_active is False and resource.is_active:
            await self._ensure_not_assigned(resource)

        for name in ("name", "type_id", "organization_id", "is_active"):
            value = getattr(data, name)
            if value is not None and getattr(resource, name) != value:
                setattr(resource, name, value)
        if data.base is not None and apply_location(resource.base, data.base):
            # La base vive en otra tabla: sin tocar la fila del recurso, `version`
            # no subiría y el bloqueo optimista no cubriría el cambio.
            resource.updated_at = datetime.now(UTC)

        await commit_or_conflict(self._session)
        return await self.get_resource(resource.id)

    async def change_status(self, resource_id: uuid.UUID, data: ResourceStatusChange) -> Resource:
        resource = await self._load_for_change(resource_id, data.version)
        if not resource.is_active:
            raise InvalidInputError("resource_inactive")
        if not can_change_status(resource.status, data.status):
            raise InvalidInputError("invalid_transition")
        # Mientras está asignado, su estado lo gobierna la asignación.
        await self._ensure_not_assigned(resource)

        resource.status = data.status
        resource.status_changed_at = datetime.now(UTC)
        await commit_or_conflict(self._session)
        return await self.get_resource(resource.id)

    # --- Internos -----------------------------------------------------------------

    async def _load_for_change(self, resource_id: uuid.UUID, version: int) -> Resource:
        # FOR UPDATE: dos cambios simultáneos sobre el mismo recurso se serializan.
        resource = await self._resources.get(resource_id, for_update=True)
        if resource is None:
            raise NotFoundError("resource_not_found")
        if resource.version != version:
            raise ConflictError("version_conflict")
        return resource

    async def _ensure_not_assigned(self, resource: Resource) -> None:
        if await self._assignments.active_for_resource(resource.id) is not None:
            raise InvalidInputError("resource_assigned")

    async def _active_type(self, type_id: uuid.UUID) -> ResourceType:
        resource_type = await self._resources.get_type(type_id)
        if resource_type is None or not resource_type.is_active:
            raise InvalidInputError("resource_type_not_found")
        return resource_type

    async def _active_organization(self, organization_id: uuid.UUID) -> Organization:
        organization = await self._organizations.get(organization_id)
        if organization is None or not organization.is_active:
            raise InvalidInputError("organization_not_found")
        return organization
