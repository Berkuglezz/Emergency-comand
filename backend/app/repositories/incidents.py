import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain.enums import IncidentPriority, IncidentStatus
from app.domain.incident_rules import ACTIVE_STATUSES, PRIORITY_RANK
from app.models import Incident, IncidentEvent, IncidentType, User
from app.models.incident import INCIDENT_CODE_SEQUENCE

INCIDENT_CODE_PREFIX = "INC-"
INCIDENT_CODE_DIGITS = 6

_PRIORITY_ORDER = case(PRIORITY_RANK, value=Incident.priority)


@dataclass(frozen=True, slots=True)
class IncidentListQuery:
    statuses: Sequence[IncidentStatus] = ()
    priorities: Sequence[IncidentPriority] = ()
    type_code: str | None = None
    active_only: bool = True
    search: str | None = None
    parent_id: uuid.UUID | None = None
    sort: str = "priority"
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True, slots=True)
class ActiveIncidentCount:
    status: IncidentStatus
    priority: IncidentPriority
    count: int
    affected_people: int


def escape_like(term: str) -> str:
    """Escapa los comodines de LIKE para buscar el texto literal."""
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class IncidentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Códigos ----------------------------------------------------------------

    async def next_code(self) -> str:
        """Siguiente código legible (`INC-000123`) de la secuencia única."""
        number = await self._session.scalar(select(INCIDENT_CODE_SEQUENCE.next_value()))
        if number is None:  # pragma: no cover — nextval siempre devuelve un valor
            raise RuntimeError("incident_code_seq no devolvió valor")
        return f"{INCIDENT_CODE_PREFIX}{number:0{INCIDENT_CODE_DIGITS}d}"

    # --- Catálogo -------------------------------------------------------------

    async def list_types(self) -> Sequence[IncidentType]:
        return (await self._session.scalars(select(IncidentType).order_by(IncidentType.code))).all()

    async def get_type(self, type_id: uuid.UUID) -> IncidentType | None:
        return await self._session.get(IncidentType, type_id)

    # --- Incidentes -----------------------------------------------------------

    def add(self, incident: Incident) -> None:
        self._session.add(incident)

    async def get(self, incident_id: uuid.UUID, *, for_update: bool = False) -> Incident | None:
        statement = (
            select(Incident)
            .where(Incident.id == incident_id)
            .options(
                joinedload(Incident.type),
                joinedload(Incident.location),
                joinedload(Incident.parent),
            )
            # Relee la fila aunque ya esté en la sesión (p. ej. tras cambiar el padre).
            .execution_options(populate_existing=True)
        )
        if for_update:
            # Bloquea la fila del incidente durante el cambio (no las del tipo,
            # la ubicación o el padre): todo cambio de ubicación pasa por ella.
            statement = statement.with_for_update(of=Incident)
        return (await self._session.scalars(statement)).unique().one_or_none()

    async def children(self, parent_id: uuid.UUID) -> Sequence[Incident]:
        statement = (
            select(Incident).where(Incident.parent_incident_id == parent_id).order_by(Incident.code)
        )
        return (await self._session.scalars(statement)).all()

    async def has_children(self, incident_id: uuid.UUID) -> bool:
        statement = select(exists().where(Incident.parent_incident_id == incident_id))
        return bool(await self._session.scalar(statement))

    async def list(self, query: IncidentListQuery) -> tuple[Sequence[Incident], int]:
        filtered = self._filtered(query)
        total = await self._session.scalar(
            select(func.count()).select_from(filtered.order_by(None).subquery())
        )
        statement = (
            filtered.options(joinedload(Incident.type), joinedload(Incident.location))
            .order_by(*self._ordering(query.sort))
            .limit(query.limit)
            .offset(query.offset)
        )
        items = (await self._session.scalars(statement)).unique().all()
        return items, total or 0

    async def count_active(self) -> Sequence[ActiveIncidentCount]:
        """Incidentes activos agrupados por estado y prioridad, con la suma de
        personas afectadas (`affected_people` nulo cuenta como 0)."""
        statement = (
            select(
                Incident.status,
                Incident.priority,
                func.count(),
                func.coalesce(func.sum(Incident.affected_people), 0),
            )
            .where(Incident.status.in_(ACTIVE_STATUSES))
            .group_by(Incident.status, Incident.priority)
        )
        return [
            ActiveIncidentCount(status, priority, count, affected or 0)
            for status, priority, count, affected in (await self._session.execute(statement)).all()
        ]

    async def count_reported_since(self, since: datetime) -> int:
        """Incidentes notificados desde `since`, en cualquier estado."""
        statement = select(func.count()).where(Incident.reported_at >= since)
        return await self._session.scalar(statement) or 0

    @staticmethod
    def _filtered(query: IncidentListQuery) -> Select[Incident]:
        statement = select(Incident)
        if query.active_only:
            statement = statement.where(Incident.status.in_(ACTIVE_STATUSES))
        if query.statuses:
            statement = statement.where(Incident.status.in_(query.statuses))
        if query.priorities:
            statement = statement.where(Incident.priority.in_(query.priorities))
        if query.type_code:
            statement = statement.join(Incident.type).where(IncidentType.code == query.type_code)
        if query.parent_id:
            statement = statement.where(Incident.parent_incident_id == query.parent_id)
        if query.search:
            pattern = f"%{escape_like(query.search)}%"
            statement = statement.where(
                or_(
                    Incident.code.ilike(pattern, escape="\\"),
                    Incident.title.ilike(pattern, escape="\\"),
                )
            )
        return statement

    @staticmethod
    def _ordering(sort: str) -> tuple[ColumnElement[Any], ...]:
        # Se ordena por el campo pedido; `id` solo desempata, para que la
        # paginación sea determinista cuando dos filas tienen el mismo valor.
        if sort == "-reported_at":
            return (Incident.reported_at.desc(), Incident.id.desc())
        if sort == "reported_at":
            return (Incident.reported_at.asc(), Incident.id.asc())
        if sort == "-updated_at":
            return (Incident.updated_at.desc(), Incident.id.desc())
        # "priority": más urgente primero y, dentro de cada prioridad, lo más reciente.
        return (_PRIORITY_ORDER.asc(), Incident.reported_at.desc(), Incident.id.desc())

    # --- Historial ------------------------------------------------------------

    def add_event(self, event: IncidentEvent) -> None:
        self._session.add(event)

    async def list_events(
        self, incident_id: uuid.UUID
    ) -> Sequence[tuple[IncidentEvent, User | None]]:
        statement = (
            select(IncidentEvent, User)
            .outerjoin(User, User.id == IncidentEvent.actor_user_id)
            .where(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.occurred_at.asc(), IncidentEvent.id.asc())
        )
        return [(event, user) for event, user in (await self._session.execute(statement)).all()]
