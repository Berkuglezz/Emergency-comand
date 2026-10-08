from fastapi import APIRouter, Depends, status

from app.api.v1.deps import DashboardServiceDep, require_permission
from app.core.permissions import Permission
from app.schemas.dashboard import DashboardSummary
from app.schemas.errors import ErrorResponse

router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
    responses={status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}},
)


@router.get(
    "/summary",
    # Agrega incidentes y recursos: exige poder leer ambos.
    dependencies=[
        Depends(require_permission(Permission.INCIDENTS_READ)),
        Depends(require_permission(Permission.RESOURCES_READ)),
    ],
)
async def get_dashboard_summary(service: DashboardServiceDep) -> DashboardSummary:
    """KPIs del centro de mando calculados con los datos actuales."""
    return await service.summary()
