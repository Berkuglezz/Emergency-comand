import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain.enums import ResourceStatus
from app.domain.resource_rules import STATUS_RANK
from app.models import Resource, ResourceType
from app.repositories.incidents import escape_like

_STATUS_ORDER = case(STATUS_RANK, value=Resource.status)


@dataclass(frozen=True, slots=True)
class ResourceListQuery:
    statuses: Sequence[ResourceStatus] = ()
    type_code: str | None = None
    organization_id: uuid.UUID | None = None
    municipality: str | None = None
    active_only: bool = True
    search: str | None = None
    sort: str = "code"
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class ResourceStatusCount:
    status: ResourceStatus
    is_active: bool
    count: int


class ResourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Catálogo -------------------------------------------------------------

    async def list_types(self) -> Sequence[ResourceType]:
        return (await self._session.scalars(select(ResourceType).order_by(ResourceType.code))).all()

    async def get_type(self, type_id: uuid.UUID) -> ResourceType | None:
        return await self._session.get(ResourceType, type_id)

    # --- Recursos -------------------------------------------------------------

    def add(self, resource: Resource) -> None:
        self._session.add(resource)

    async def get(self, resource_id: uuid.UUID, *, for_update: bool = False) -> Resource | None:
        statement = (
            select(Resource)
            .where(Resource.id == resource_id)
            .options(joinedload(Resource.type), joinedload(Resource.organization))
            # Relee la fila aunque ya esté en la sesión (p. ej. tras cambiar el tipo).
            .execution_options(populate_existing=True)
        )
        if for_update:
            # Bloquea solo la fila del recurso, no las del tipo o la organización.
            statement = statement.with_for_update(of=Resource)
        return (await self._session.scalars(statement)).unique().one_or_none()

    async def code_exists(self, code: str) -> bool:
        return bool(await self._session.scalar(select(func.count()).where(Resource.code == code)))

    async def list(self, query: ResourceListQuery) -> tuple[Sequence[Resource], int]:
        filtered = self._filtered(query)
        total = await self._session.scalar(
            select(func.count()).select_from(filtered.order_by(None).subquery())
        )
        statement = (
            filtered.options(joinedload(Resource.type), joinedload(Resource.organization))
            .order_by(*self._ordering(query.sort))
            .limit(query.limit)
            .offset(query.offset)
        )
        items = (await self._session.scalars(statement)).unique().all()
        return items, total or 0

    async def count_by_status(self) -> Sequence[ResourceStatusCount]:
        """Recuento de recursos por estado y por si están activos o no."""
        statement = select(Resource.status, Resource.is_active, func.count()).group_by(
            Resource.status, Resource.is_active
        )
        return [
            ResourceStatusCount(status, is_active, count)
            for status, is_active, count in (await self._session.execute(statement)).all()
        ]

    @staticmethod
    def _filtered(query: ResourceListQuery) -> Select[Resource]:
        statement = select(Resource)
        if query.active_only:
            statement = statement.where(Resource.is_active.is_(True))
        if query.statuses:
            statement = statement.where(Resource.status.in_(query.statuses))
        if query.type_code:
            statement = statement.join(Resource.type).where(ResourceType.code == query.type_code)
        if query.organization_id:
            statement = statement.where(Resource.organization_id == query.organization_id)
        if query.municipality:
            statement = statement.where(
                func.lower(Resource.municipality) == query.municipality.lower()
            )
        if query.search:
            pattern = f"%{escape_like(query.search)}%"
            statement = statement.where(
                or_(
                    Resource.code.ilike(pattern, escape="\\"),
                    Resource.name.ilike(pattern, escape="\\"),
                )
            )
        return statement

    @staticmethod
    def _ordering(sort: str) -> tuple[ColumnElement[Any], ...]:
        # `id` solo desempata, para que la paginación sea determinista.
        if sort == "status":
            return (_STATUS_ORDER.asc(), Resource.code.asc(), Resource.id.asc())
        if sort == "-status_changed_at":
            return (Resource.status_changed_at.desc(), Resource.id.desc())
        return (Resource.code.asc(), Resource.id.asc())
