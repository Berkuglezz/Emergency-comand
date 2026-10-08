"""KPIs del centro de mando, agregados a partir de incidentes y recursos."""

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import IncidentPriority, IncidentStatus, ResourceStatus
from app.domain.incident_rules import ACTIVE_STATUSES
from app.repositories.incidents import IncidentRepository
from app.repositories.resources import ResourceRepository
from app.schemas.dashboard import DashboardSummary, IncidentKpis, ResourceKpis

RECENT_WINDOW = timedelta(hours=24)


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self._incidents = IncidentRepository(session)
        self._resources = ResourceRepository(session)

    async def summary(self) -> DashboardSummary:
        now = datetime.now(UTC)
        return DashboardSummary(
            generated_at=now,
            incidents=await self._incident_kpis(now),
            resources=await self._resource_kpis(),
        )

    async def _incident_kpis(self, now: datetime) -> IncidentKpis:
        by_priority = dict.fromkeys(IncidentPriority, 0)
        # Solo los estados activos, en el orden del enum.
        by_status = {status: 0 for status in IncidentStatus if status in ACTIVE_STATUSES}
        affected = 0
        for row in await self._incidents.count_active():
            by_priority[row.priority] += row.count
            by_status[row.status] += row.count
            affected += row.affected_people
        return IncidentKpis(
            active_total=sum(by_priority.values()),
            by_priority=by_priority,
            by_status=by_status,
            affected_people=affected,
            reported_last_24h=await self._incidents.count_reported_since(now - RECENT_WINDOW),
        )

    async def _resource_kpis(self) -> ResourceKpis:
        by_status = dict.fromkeys(ResourceStatus, 0)
        inactive = 0
        for row in await self._resources.count_by_status():
            if row.is_active:
                by_status[row.status] += row.count
            else:
                inactive += row.count
        return ResourceKpis(
            active_total=sum(by_status.values()),
            by_status=by_status,
            inactive_total=inactive,
        )
