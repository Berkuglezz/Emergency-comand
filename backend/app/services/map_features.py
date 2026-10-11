"""Mapa operativo (CLAUDE.md §2.12): perímetros y demás geometrías de un incidente.

- Solo `incidents:read` para consultar; `map_features:manage` para crear,
  editar y retirar (lo comprueba el router; coordinador y admin, D-M2).
- Validación: forma en el dominio puro (`app.domain.map_features`) y validez
  topológica en PostGIS (`ST_IsValid`), con un CHECK más en la tabla.
- Cada cambio y su evento del historial (geometría anterior y nueva, D-M3) van
  en la misma transacción. Retirar no borra (D-M4).
- Orden de bloqueos (como el resto del backend): primero el incidente y
  después el elemento. Editar un elemento no modifica la fila del incidente ni
  su `version` (D-M7).
- Las geometrías nunca se escriben en logs ni en mensajes de error.
"""

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import IncidentEventType, MapFeatureKind, MapFeatureStatus
from app.domain.exceptions import ConflictError, InvalidInputError, NotFoundError
from app.domain.incident_rules import TERMINAL_STATUSES
from app.domain.map_features import (
    GEOMETRY_TYPE_BY_KIND,
    PolygonGeometry,
    ensure_event_payload_size,
    ensure_kind_enabled,
    validate_polygon,
)
from app.models import Incident, IncidentMapFeature, User
from app.models.incident_map_feature import geometry_element
from app.repositories.incidents import IncidentRepository
from app.repositories.map_features import MapFeatureRepository
from app.schemas.map_features import (
    GeometryInput,
    MapFeatureCreate,
    MapFeatureRetire,
    MapFeatureUpdate,
)
from app.services.incident_events import EventRecorder
from app.services.transactions import commit_or_conflict

# Campos que no admiten `null` en una edición.
_NOT_NULLABLE = frozenset({"geometry"})


class MapFeatureService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._features = MapFeatureRepository(session)
        self._incidents = IncidentRepository(session)

    # --- Lectura ----------------------------------------------------------------

    async def list_for_incident(
        self, incident_id: uuid.UUID, *, include_retired: bool
    ) -> Sequence[IncidentMapFeature]:
        if await self._incidents.get(incident_id) is None:
            raise NotFoundError("incident_not_found")
        return await self._features.list_for_incident(incident_id, include_retired=include_retired)

    async def get(self, feature_id: uuid.UUID) -> IncidentMapFeature:
        feature = await self._features.get(feature_id)
        if feature is None:
            raise NotFoundError("map_feature_not_found")
        return feature

    # --- Escritura --------------------------------------------------------------

    async def create(
        self, incident_id: uuid.UUID, data: MapFeatureCreate, actor: User
    ) -> IncidentMapFeature:
        ensure_kind_enabled(data.kind)
        geometry = _validate(data.kind, data.geometry)
        incident = await self._open_incident(incident_id)
        await self._ensure_topology(geometry)

        now = datetime.now(UTC)
        feature = IncidentMapFeature(
            incident_id=incident.id,
            kind=data.kind,
            status=MapFeatureStatus.ACTIVE,
            geom=geometry_element(geometry.as_wkt()),
            label=data.label,
            note=data.note or None,
            created_by_id=actor.id,
            updated_by_id=actor.id,
            is_simulated=incident.is_simulated,
            created_at=now,
            updated_at=now,
        )
        self._features.add(feature)
        await self._session.flush()
        self._record(
            incident,
            actor,
            now,
            IncidentEventType.MAP_FEATURE_ADDED,
            feature,
            before=None,
            after=geometry.as_geojson(),
        )
        await commit_or_conflict(self._session)
        return await self.get(feature.id)

    async def update(
        self, feature_id: uuid.UUID, data: MapFeatureUpdate, actor: User
    ) -> IncidentMapFeature:
        """Edición parcial. Si nada cambia de verdad, no se escribe nada: ni
        evento ni `version` nueva."""
        sent = data.model_fields_set - {"version"}
        if any(getattr(data, name) is None for name in sent & _NOT_NULLABLE):
            raise InvalidInputError("field_not_nullable")
        incident, feature = await self._load_for_change(feature_id, data.version)

        geometry: PolygonGeometry | None = None
        if data.geometry is not None:
            geometry = _validate(feature.kind, data.geometry)
        before = _geojson(feature)
        changed: list[str] = []
        if geometry is not None and geometry.as_geojson() != before:
            await self._ensure_topology(geometry)
            feature.geom = geometry_element(geometry.as_wkt())
            changed.append("geometry")
        for name in ("label", "note"):
            if name in sent:
                value = getattr(data, name) or None
                if getattr(feature, name) != value:
                    setattr(feature, name, value)
                    changed.append(name)
        if not changed:
            return await self.get(feature.id)

        now = datetime.now(UTC)
        feature.updated_by_id = actor.id
        feature.updated_at = now
        self._record(
            incident,
            actor,
            now,
            IncidentEventType.MAP_FEATURE_UPDATED,
            feature,
            before=before,
            after=geometry.as_geojson() if geometry is not None else before,
            extra={"fields": sorted(changed)},
        )
        await commit_or_conflict(self._session)
        return await self.get(feature.id)

    async def retire(
        self, feature_id: uuid.UUID, data: MapFeatureRetire, actor: User
    ) -> IncidentMapFeature:
        """Retira el elemento (no lo borra): deja de mostrarse como activo y el
        historial conserva su última geometría."""
        incident, feature = await self._load_for_change(feature_id, data.version)
        now = datetime.now(UTC)
        before = _geojson(feature)
        feature.status = MapFeatureStatus.RETIRED
        feature.retired_at = now
        feature.retired_by_id = actor.id
        feature.retire_reason = data.reason
        feature.updated_by_id = actor.id
        feature.updated_at = now
        self._record(
            incident,
            actor,
            now,
            IncidentEventType.MAP_FEATURE_RETIRED,
            feature,
            before=before,
            after=None,
            extra={"reason": data.reason},
        )
        await commit_or_conflict(self._session)
        return await self.get(feature.id)

    # --- Internos ---------------------------------------------------------------

    async def _open_incident(self, incident_id: uuid.UUID) -> Incident:
        # FOR UPDATE: ni se cierra el incidente ni se edita otra geometría suya
        # mientras dura el cambio. No se modifica su fila ni su `version`.
        incident = await self._incidents.get(incident_id, for_update=True)
        if incident is None:
            raise NotFoundError("incident_not_found")
        if incident.status in TERMINAL_STATUSES:
            raise InvalidInputError("incident_closed")
        return incident

    async def _load_for_change(
        self, feature_id: uuid.UUID, version: int
    ) -> tuple[Incident, IncidentMapFeature]:
        found = await self._features.get(feature_id)
        if found is None:
            raise NotFoundError("map_feature_not_found")
        # Orden global de bloqueos: el incidente antes que el elemento.
        incident = await self._open_incident(found.incident_id)
        feature = await self._features.get(feature_id, for_update=True)
        if feature is None:  # pragma: no cover — los elementos no se borran
            raise NotFoundError("map_feature_not_found")
        if feature.version != version:
            raise ConflictError("version_conflict")
        if feature.status == MapFeatureStatus.RETIRED:
            raise InvalidInputError("map_feature_retired")
        return incident, feature

    async def _ensure_topology(self, geometry: PolygonGeometry) -> None:
        if not await self._features.is_valid_geometry(geometry.as_wkt()):
            raise InvalidInputError("geometry_invalid_topology")

    def _record(
        self,
        incident: Incident,
        actor: User,
        now: datetime,
        event_type: IncidentEventType,
        feature: IncidentMapFeature,
        *,
        before: dict[str, Any] | None,
        after: dict[str, Any] | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "feature_id": str(feature.id),
            "kind": feature.kind,
            "label": feature.label,
            "before": before,
            "after": after,
            **(extra or {}),
        }
        ensure_event_payload_size(payload)
        EventRecorder(self._incidents, actor, now).record(incident, event_type, payload)


def _validate(kind: MapFeatureKind, geometry: GeometryInput) -> PolygonGeometry:
    if GEOMETRY_TYPE_BY_KIND[kind] != geometry.type:
        raise InvalidInputError("geometry_kind_mismatch")
    if geometry.type != "Polygon":  # pragma: no cover — solo hay tipos de área habilitados
        raise InvalidInputError("map_feature_kind_not_enabled")
    return validate_polygon(kind, geometry.type, geometry.coordinates)


def _geojson(feature: IncidentMapFeature) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(feature.geojson)
    return value
