"""Mapa operativo (CLAUDE.md §2.12): geometrías dibujadas sobre un incidente.

Consultar exige `incidents:read`; crear, editar y retirar, `map_features:manage`
(coordinador y admin). En esta versión solo se admite el tipo `perimeter`.
"""

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, status

from app.api.v1.deps import CurrentUserDep, MapFeatureServiceDep, require_permission
from app.core.permissions import Permission
from app.models import IncidentMapFeature, User
from app.schemas.errors import ErrorResponse
from app.schemas.incidents import EventActor
from app.schemas.map_features import (
    MapFeatureCollection,
    MapFeatureCreate,
    MapFeatureGeometry,
    MapFeatureProperties,
    MapFeatureResponse,
    MapFeatureRetire,
    MapFeatureUpdate,
)

_ERRORS: dict[int | str, dict[str, Any]] = {
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse},
    status.HTTP_409_CONFLICT: {"model": ErrorResponse},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": ErrorResponse},
}

_READ = [Depends(require_permission(Permission.INCIDENTS_READ))]
_MANAGE = [Depends(require_permission(Permission.MAP_FEATURES_MANAGE))]

incident_router = APIRouter(prefix="/incidents", tags=["map-features"], responses=_ERRORS)
router = APIRouter(prefix="/map-features", tags=["map-features"], responses=_ERRORS)


def _actor(user: User | None) -> EventActor | None:
    return EventActor(id=user.id, full_name=user.full_name) if user else None


def _feature(feature: IncidentMapFeature) -> MapFeatureResponse:
    return MapFeatureResponse(
        id=feature.id,
        geometry=MapFeatureGeometry.model_validate(json.loads(feature.geojson)),
        properties=MapFeatureProperties(
            incident_id=feature.incident_id,
            kind=feature.kind,
            status=feature.status,
            label=feature.label,
            note=feature.note,
            version=feature.version,
            created_at=feature.created_at,
            created_by=_actor(feature.created_by),
            updated_at=feature.updated_at,
            updated_by=_actor(feature.updated_by),
            retired_at=feature.retired_at,
            retired_by=_actor(feature.retired_by),
            retire_reason=feature.retire_reason,
            is_simulated=feature.is_simulated,
        ),
    )


@incident_router.get("/{incident_id}/map-features", dependencies=_READ)
async def list_map_features(
    incident_id: uuid.UUID, service: MapFeatureServiceDep, include_retired: bool = False
) -> MapFeatureCollection:
    """Geometrías del incidente como `FeatureCollection` GeoJSON. Por defecto
    solo las activas; `include_retired=true` añade las retiradas."""
    features = await service.list_for_incident(incident_id, include_retired=include_retired)
    return MapFeatureCollection(features=[_feature(feature) for feature in features])


@incident_router.post(
    "/{incident_id}/map-features", status_code=status.HTTP_201_CREATED, dependencies=_MANAGE
)
async def create_map_feature(
    incident_id: uuid.UUID,
    body: MapFeatureCreate,
    user: CurrentUserDep,
    service: MapFeatureServiceDep,
) -> MapFeatureResponse:
    """Dibuja una geometría sobre el incidente (en esta versión, un perímetro)."""
    return _feature(await service.create(incident_id, body, user))


@router.patch("/{feature_id}", dependencies=_MANAGE)
async def update_map_feature(
    feature_id: uuid.UUID,
    body: MapFeatureUpdate,
    user: CurrentUserDep,
    service: MapFeatureServiceDep,
) -> MapFeatureResponse:
    """Edita geometría, etiqueta o nota con la `version` del elemento."""
    return _feature(await service.update(feature_id, body, user))


@router.post("/{feature_id}/retire", dependencies=_MANAGE)
async def retire_map_feature(
    feature_id: uuid.UUID,
    body: MapFeatureRetire,
    user: CurrentUserDep,
    service: MapFeatureServiceDep,
) -> MapFeatureResponse:
    """Retira el elemento con un motivo. No se borra: queda en el historial."""
    return _feature(await service.retire(feature_id, body, user))
