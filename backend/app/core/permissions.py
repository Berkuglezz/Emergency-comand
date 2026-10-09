"""Mapa rol → permisos (RBAC). Fuente de verdad de la autorización.

Los permisos se comprueban siempre en el backend (`require_permission`). El
frontend recibe la lista de permisos en `/auth/me` solo para adaptar la
navegación; ocultar opciones no es una medida de seguridad.
"""

from enum import StrEnum

from app.domain.enums import RoleCode


class Permission(StrEnum):
    INCIDENTS_READ = "incidents:read"
    INCIDENTS_CREATE = "incidents:create"
    INCIDENTS_UPDATE = "incidents:update"
    # Cerrar o cancelar un incidente.
    INCIDENTS_CLOSE = "incidents:close"
    RESOURCES_READ = "resources:read"
    RESOURCES_UPDATE_STATUS = "resources:update_status"
    # Alta y edición de la ficha de un recurso (incluida la desactivación).
    RESOURCES_MANAGE = "resources:manage"
    ORGANIZATIONS_READ = "organizations:read"
    # Asignar, retirar y reasignar recursos a incidentes.
    ASSIGNMENTS_MANAGE = "assignments:manage"
    # Marcar que un recurso asignado ha llegado al lugar.
    ASSIGNMENTS_UPDATE = "assignments:update"


P = Permission

ROLE_PERMISSIONS: dict[RoleCode, frozenset[Permission]] = {
    RoleCode.ADMIN: frozenset(Permission),
    RoleCode.COORDINATOR: frozenset(
        {
            P.INCIDENTS_READ,
            P.INCIDENTS_CREATE,
            P.INCIDENTS_UPDATE,
            P.INCIDENTS_CLOSE,
            P.RESOURCES_READ,
            P.RESOURCES_UPDATE_STATUS,
            P.ORGANIZATIONS_READ,
            P.ASSIGNMENTS_MANAGE,
            P.ASSIGNMENTS_UPDATE,
        }
    ),
    # Usuario operativo: consulta incidentes, actualiza el estado de recursos y
    # marca la llegada de los asignados (no asigna ni retira).
    RoleCode.OPERATOR: frozenset(
        {
            P.INCIDENTS_READ,
            P.RESOURCES_READ,
            P.RESOURCES_UPDATE_STATUS,
            P.ASSIGNMENTS_UPDATE,
        }
    ),
}


def permissions_for(role: RoleCode) -> frozenset[Permission]:
    return ROLE_PERMISSIONS[role]


def has_permission(role: RoleCode, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
