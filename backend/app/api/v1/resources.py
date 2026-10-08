import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.deps import ResourceServiceDep, require_permission
from app.core.permissions import Permission
from app.domain.enums import ResourceStatus
from app.repositories.resources import ResourceListQuery
from app.schemas.errors import ErrorResponse
from app.schemas.resources import (
    ResourceCreate,
    ResourcePage,
    ResourceResponse,
    ResourceSort,
    ResourceStatusChange,
    ResourceTypeResponse,
    ResourceUpdate,
)

_ERRORS: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}

_READ = [Depends(require_permission(Permission.RESOURCES_READ))]
_MANAGE = [Depends(require_permission(Permission.RESOURCES_MANAGE))]
_UPDATE_STATUS = [Depends(require_permission(Permission.RESOURCES_UPDATE_STATUS))]

types_router = APIRouter(prefix="/resource-types", tags=["resources"], responses=_ERRORS)
router = APIRouter(prefix="/resources", tags=["resources"], responses=_ERRORS)


@types_router.get("", dependencies=_READ)
async def list_resource_types(service: ResourceServiceDep) -> list[ResourceTypeResponse]:
    return [ResourceTypeResponse.model_validate(t) for t in await service.list_types()]


@router.get("", dependencies=_READ)
async def list_resources(
    service: ResourceServiceDep,
    status_filter: Annotated[list[ResourceStatus] | None, Query(alias="status")] = None,
    type_code: Annotated[str | None, Query(alias="type", max_length=64)] = None,
    organization_id: uuid.UUID | None = None,
    municipality: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    active: bool = True,
    q: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    sort: ResourceSort = "code",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ResourcePage:
    """Recursos. Por defecto solo los activos (`active=false` incluye los desactivados)."""
    query = ResourceListQuery(
        statuses=status_filter or (),
        type_code=type_code,
        organization_id=organization_id,
        municipality=municipality,
        active_only=active,
        search=q,
        sort=sort,
        limit=limit,
        offset=offset,
    )
    items, total = await service.list_resources(query)
    return ResourcePage(
        items=[ResourceResponse.model_validate(item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=_MANAGE)
async def create_resource(body: ResourceCreate, service: ResourceServiceDep) -> ResourceResponse:
    return ResourceResponse.model_validate(await service.create_resource(body))


@router.get("/{resource_id}", dependencies=_READ)
async def get_resource(resource_id: uuid.UUID, service: ResourceServiceDep) -> ResourceResponse:
    return ResourceResponse.model_validate(await service.get_resource(resource_id))


@router.patch("/{resource_id}", dependencies=_MANAGE)
async def update_resource(
    resource_id: uuid.UUID, body: ResourceUpdate, service: ResourceServiceDep
) -> ResourceResponse:
    """Edita la ficha (incluida la desactivación con `is_active`). No cambia el estado."""
    return ResourceResponse.model_validate(await service.update_resource(resource_id, body))


@router.post("/{resource_id}/status", dependencies=_UPDATE_STATUS)
async def change_resource_status(
    resource_id: uuid.UUID, body: ResourceStatusChange, service: ResourceServiceDep
) -> ResourceResponse:
    return ResourceResponse.model_validate(await service.change_status(resource_id, body))
