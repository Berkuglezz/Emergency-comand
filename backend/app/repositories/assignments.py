import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models import Incident, Resource, ResourceAssignment, ResourceType


class AssignmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, assignment: ResourceAssignment) -> None:
        self._session.add(assignment)

    async def get(
        self, assignment_id: uuid.UUID, *, for_update: bool = False
    ) -> ResourceAssignment | None:
        statement = select(ResourceAssignment).where(ResourceAssignment.id == assignment_id)
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def active_for_resource(
        self, resource_id: uuid.UUID, *, for_update: bool = False
    ) -> ResourceAssignment | None:
        statement = select(ResourceAssignment).where(
            ResourceAssignment.resource_id == resource_id,
            ResourceAssignment.released_at.is_(None),
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def active_for_incident(
        self, incident_id: uuid.UUID, *, for_update: bool = False
    ) -> Sequence[ResourceAssignment]:
        statement = (
            select(ResourceAssignment)
            .where(
                ResourceAssignment.incident_id == incident_id,
                ResourceAssignment.released_at.is_(None),
            )
            .order_by(ResourceAssignment.assigned_at, ResourceAssignment.id)
        )
        if for_update:
            statement = statement.with_for_update()
        return (await self._session.scalars(statement)).all()

    async def list_for_incident(self, incident_id: uuid.UUID) -> Sequence[ResourceAssignment]:
        """Activas primero (por hora de asignación) y después el historial."""
        statement = (
            select(ResourceAssignment)
            .where(ResourceAssignment.incident_id == incident_id)
            .options(
                joinedload(ResourceAssignment.resource).joinedload(Resource.type),
                joinedload(ResourceAssignment.resource).joinedload(Resource.organization),
                joinedload(ResourceAssignment.resource).joinedload(Resource.base),
            )
            .order_by(
                ResourceAssignment.released_at.is_not(None),
                ResourceAssignment.assigned_at,
                ResourceAssignment.id,
            )
        )
        return (await self._session.scalars(statement)).unique().all()

    async def count_active(self, incident_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]:
        ids = list(incident_ids)
        if not ids:
            return {}
        statement = (
            select(ResourceAssignment.incident_id, func.count())
            .where(
                ResourceAssignment.incident_id.in_(ids),
                ResourceAssignment.released_at.is_(None),
            )
            .group_by(ResourceAssignment.incident_id)
        )
        return {incident_id: count for incident_id, count in await self._session.execute(statement)}

    async def current_for_resources(
        self, resource_ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[ResourceAssignment, str]]:
        """Asignación activa de cada recurso, con el código de su incidente."""
        ids = list(resource_ids)
        if not ids:
            return {}
        statement = (
            select(ResourceAssignment, Incident.code)
            .join(Incident, Incident.id == ResourceAssignment.incident_id)
            .where(
                ResourceAssignment.resource_id.in_(ids),
                ResourceAssignment.released_at.is_(None),
            )
        )
        return {
            assignment.resource_id: (assignment, code)
            for assignment, code in await self._session.execute(statement)
        }

    async def candidate_resources(
        self,
        *,
        type_code: str | None,
        organization_id: uuid.UUID | None,
        organization_ids: frozenset[uuid.UUID] | None = None,
    ) -> Sequence[Resource]:
        """Recursos activos que no están fuera de servicio, con tipo y base.
        `organization_ids` limita a esas organizaciones (ámbito); `None`, a todas."""
        statement = (
            select(Resource)
            .where(Resource.is_active.is_(True))
            .options(
                joinedload(Resource.type),
                joinedload(Resource.organization),
                joinedload(Resource.base),
            )
        )
        if type_code:
            statement = statement.join(Resource.type).where(ResourceType.code == type_code)
        if organization_id:
            statement = statement.where(Resource.organization_id == organization_id)
        if organization_ids is not None:
            statement = statement.where(Resource.organization_id.in_(organization_ids))
        return (await self._session.scalars(statement)).unique().all()
