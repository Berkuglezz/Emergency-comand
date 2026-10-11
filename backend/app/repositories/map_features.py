import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain.enums import MapFeatureStatus
from app.models import IncidentMapFeature
from app.models.location import LOCATION_SRID


class MapFeatureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, feature: IncidentMapFeature) -> None:
        self._session.add(feature)

    async def get(
        self, feature_id: uuid.UUID, *, for_update: bool = False
    ) -> IncidentMapFeature | None:
        statement = (
            select(IncidentMapFeature)
            .where(IncidentMapFeature.id == feature_id)
            .options(*_RELATIONS)
            # Relee la fila (y su GeoJSON calculado) aunque ya esté en la sesión.
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update(of=IncidentMapFeature)
        return (await self._session.scalars(statement)).unique().one_or_none()

    async def list_for_incident(
        self, incident_id: uuid.UUID, *, include_retired: bool
    ) -> Sequence[IncidentMapFeature]:
        statement = (
            select(IncidentMapFeature)
            .where(IncidentMapFeature.incident_id == incident_id)
            .options(*_RELATIONS)
            .order_by(IncidentMapFeature.created_at, IncidentMapFeature.id)
        )
        if not include_retired:
            statement = statement.where(IncidentMapFeature.status == MapFeatureStatus.ACTIVE)
        return (await self._session.scalars(statement)).unique().all()

    async def is_valid_geometry(self, wkt: str) -> bool:
        """Validez topológica según PostGIS (`ST_IsValid`): detecta, entre otras
        cosas, autointersecciones. La geometría no se registra en ningún log."""
        valid = await self._session.scalar(
            select(func.ST_IsValid(func.ST_GeomFromText(wkt, LOCATION_SRID)))
        )
        return bool(valid)


_RELATIONS = (
    joinedload(IncidentMapFeature.created_by),
    joinedload(IncidentMapFeature.updated_by),
    joinedload(IncidentMapFeature.retired_by),
)
