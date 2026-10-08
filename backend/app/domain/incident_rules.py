"""Reglas puras del ciclo de vida de un incidente (sin I/O).

Flujo operativo de la Fase 2:

    received → assessing → in_progress → controlled → closed
                                    ↑__________|            (reapertura)

    cancelled: desde received, assessing o in_progress.

`resources_assigned` existe en el modelo pero no es alcanzable: se habilitará
cuando exista la asignación de recursos (fase posterior).
"""

from app.domain.enums import IncidentPriority, IncidentStatus

S = IncidentStatus

ALLOWED_TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    S.RECEIVED: frozenset({S.ASSESSING, S.CANCELLED}),
    S.ASSESSING: frozenset({S.IN_PROGRESS, S.CANCELLED}),
    S.RESOURCES_ASSIGNED: frozenset(),
    S.IN_PROGRESS: frozenset({S.CONTROLLED, S.CANCELLED}),
    S.CONTROLLED: frozenset({S.CLOSED, S.IN_PROGRESS}),
    S.CLOSED: frozenset(),
    S.CANCELLED: frozenset(),
}

INITIAL_STATUS = S.RECEIVED

TERMINAL_STATUSES: frozenset[IncidentStatus] = frozenset({S.CLOSED, S.CANCELLED})

# Un incidente está activo mientras no se haya cerrado ni cancelado.
ACTIVE_STATUSES: frozenset[IncidentStatus] = frozenset(IncidentStatus) - TERMINAL_STATUSES

# Transiciones que exigen el permiso `incidents:close`.
CLOSING_STATUSES: frozenset[IncidentStatus] = TERMINAL_STATUSES

# Orden de prioridad para ordenar listados (menor = más urgente).
PRIORITY_RANK: dict[IncidentPriority, int] = {
    IncidentPriority.CRITICAL: 0,
    IncidentPriority.HIGH: 1,
    IncidentPriority.MEDIUM: 2,
    IncidentPriority.LOW: 3,
}


def can_transition(current: IncidentStatus, target: IncidentStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]


def allowed_transitions(current: IncidentStatus) -> list[IncidentStatus]:
    """Estados de destino válidos, en el orden del enum (estable para la UI)."""
    return [status for status in IncidentStatus if status in ALLOWED_TRANSITIONS[current]]


def is_active(status: IncidentStatus) -> bool:
    return status in ACTIVE_STATUSES


def reachable_statuses() -> frozenset[IncidentStatus]:
    """Estados alcanzables desde el inicial siguiendo las transiciones."""
    seen = {INITIAL_STATUS}
    pending = [INITIAL_STATUS]
    while pending:
        for target in ALLOWED_TRANSITIONS[pending.pop()]:
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return frozenset(seen)
