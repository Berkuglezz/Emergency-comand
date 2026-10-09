"""Reglas puras de la asignación de recursos a incidentes (CLAUDE.md §2.8).

Principio: el sistema informa, la persona responsable decide y el sistema
ejecuta. Aquí no hay ninguna selección automática de recursos.
"""

from app.domain.enums import ReleaseReason, ResourceStatus

# Motivos que puede elegir una persona al retirar un recurso. `reassigned` e
# `incident_closed` los pone el sistema.
USER_RELEASE_REASONS: frozenset[ReleaseReason] = frozenset(
    {ReleaseReason.COMPLETED, ReleaseReason.NOT_NEEDED, ReleaseReason.UNAVAILABLE}
)


def assignment_blocker(*, is_active: bool, status: ResourceStatus) -> str | None:
    """Código de error si el recurso no se puede asignar; `None` si se puede.

    Un recurso ya asignado a otro incidente se comprueba aparte (reasignación).
    """
    if not is_active:
        return "resource_inactive"
    if status != ResourceStatus.AVAILABLE:
        return "resource_not_available"
    return None


def resource_status_after_release(reason: ReleaseReason) -> ResourceStatus:
    """Retirado por avería o incidencia → fuera de servicio; si no, disponible."""
    if reason == ReleaseReason.UNAVAILABLE:
        return ResourceStatus.OUT_OF_SERVICE
    return ResourceStatus.AVAILABLE
