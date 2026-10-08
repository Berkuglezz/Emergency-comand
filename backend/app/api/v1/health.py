from fastapi import APIRouter, Response, status

from app.api.v1.deps import HealthServiceDep
from app.domain.enums import HealthStatus
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
async def get_health(response: Response, service: HealthServiceDep) -> HealthResponse:
    """Estado del backend y de sus dependencias. Público."""
    health = await service.check()
    if health.status is not HealthStatus.OK:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return health
