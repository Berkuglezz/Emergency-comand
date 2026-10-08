from fastapi import APIRouter, Depends, status

from app.api.v1.deps import OrganizationServiceDep, require_permission
from app.core.permissions import Permission
from app.schemas.errors import ErrorResponse
from app.schemas.organizations import OrganizationResponse

router = APIRouter(
    prefix="/organizations",
    tags=["organizations"],
    responses={status.HTTP_403_FORBIDDEN: {"model": ErrorResponse}},
)


@router.get("", dependencies=[Depends(require_permission(Permission.ORGANIZATIONS_READ))])
async def list_organizations(service: OrganizationServiceDep) -> list[OrganizationResponse]:
    organizations = await service.list_organizations()
    return [OrganizationResponse.model_validate(org) for org in organizations]
