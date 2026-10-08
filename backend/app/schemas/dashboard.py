"""Resumen del centro de mando: KPIs calculados con los datos reales de la BD.

Los recuentos por código incluyen siempre todas las claves (con 0 si no hay
filas), para que el frontend no tenga que suponer valores ausentes.
"""

from datetime import datetime

from pydantic import BaseModel

from app.domain.enums import IncidentPriority, IncidentStatus, ResourceStatus


class IncidentKpis(BaseModel):
    active_total: int
    # Solo incidentes activos (ni cerrados ni cancelados).
    by_priority: dict[IncidentPriority, int]
    by_status: dict[IncidentStatus, int]
    # Suma de `affected_people` de los incidentes activos (sin dato = 0).
    affected_people: int
    # Incidentes notificados en las últimas 24 h, en cualquier estado.
    reported_last_24h: int


class ResourceKpis(BaseModel):
    # Solo recursos activos (`is_active`); los desactivados se cuentan aparte.
    active_total: int
    by_status: dict[ResourceStatus, int]
    inactive_total: int


class DashboardSummary(BaseModel):
    generated_at: datetime
    incidents: IncidentKpis
    resources: ResourceKpis
