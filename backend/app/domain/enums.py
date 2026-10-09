"""Enumeraciones de dominio (códigos estables; el frontend los traduce)."""

from enum import StrEnum


class RoleCode(StrEnum):
    ADMIN = "admin"
    COORDINATOR = "coordinator"
    OPERATOR = "operator"


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"


class ComponentStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"


# --- Incidentes (CLAUDE.md §5: estados y prioridades fijos, comunes a todos los tipos) ---


class IncidentStatus(StrEnum):
    RECEIVED = "received"
    ASSESSING = "assessing"
    # Solo se alcanza automáticamente al asignar recursos (Fase 4). Ver
    # `domain/incident_rules.py`.
    RESOURCES_ASSIGNED = "resources_assigned"
    IN_PROGRESS = "in_progress"
    CONTROLLED = "controlled"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class IncidentPriority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentCategory(StrEnum):
    FIRE = "fire"
    TRAFFIC = "traffic"
    MEDICAL = "medical"
    RESCUE = "rescue"
    WEATHER = "weather"
    HAZMAT = "hazmat"
    GEOLOGICAL = "geological"


class IncidentEventType(StrEnum):
    """Tipos de entrada del historial funcional del incidente (timeline)."""

    INCIDENT_CREATED = "incident_created"
    STATUS_CHANGED = "status_changed"
    PRIORITY_CHANGED = "priority_changed"
    INCIDENT_UPDATED = "incident_updated"
    NOTE_ADDED = "note_added"
    PARENT_CHANGED = "parent_changed"
    LOCATION_CHANGED = "location_changed"
    RESOURCE_ASSIGNED = "resource_assigned"
    RESOURCE_ARRIVED = "resource_arrived"
    RESOURCE_RELEASED = "resource_released"


# --- Recursos ---------------------------------------------------------------


class ResourceCategory(StrEnum):
    FIRE = "fire"
    RESCUE = "rescue"
    MEDICAL = "medical"
    COMMAND = "command"
    CIVIL_PROTECTION = "civil_protection"
    LOGISTICS = "logistics"


class ResourceStatus(StrEnum):
    AVAILABLE = "available"
    IN_SERVICE = "in_service"
    OUT_OF_SERVICE = "out_of_service"


class ReleaseReason(StrEnum):
    """Motivo de la retirada de un recurso de un incidente."""

    COMPLETED = "completed"
    NOT_NEEDED = "not_needed"
    UNAVAILABLE = "unavailable"
    # Los dos siguientes los pone el sistema.
    REASSIGNED = "reassigned"
    INCIDENT_CLOSED = "incident_closed"


class StatusChangeCause(StrEnum):
    """Causa de un cambio de estado automático del incidente."""

    ASSIGNMENT = "assignment"
