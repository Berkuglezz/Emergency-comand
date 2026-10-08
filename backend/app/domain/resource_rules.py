"""Reglas puras del estado operativo de un recurso (sin I/O).

En la Fase 2 no hay asignaciones: el estado lo cambia una persona
directamente, entre cualquiera de los tres valores. Un recurso desactivado
(`is_active = false`) no cambia de estado hasta que se reactive.
"""

from app.domain.enums import ResourceStatus

INITIAL_STATUS = ResourceStatus.AVAILABLE

# Orden para listados: primero lo disponible.
STATUS_RANK: dict[ResourceStatus, int] = {
    ResourceStatus.AVAILABLE: 0,
    ResourceStatus.IN_SERVICE: 1,
    ResourceStatus.OUT_OF_SERVICE: 2,
}


def can_change_status(current: ResourceStatus, target: ResourceStatus) -> bool:
    """Cualquier cambio entre los tres estados; repetir el actual no es un cambio."""
    return current != target
