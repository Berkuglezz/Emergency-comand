"""Reglas puras del ciclo de vida de un incidente (sin I/O).

Transiciones manuales:

    received → assessing → in_progress → controlled → closed
                                    ↑__________|            (reapertura)
    resources_assigned → in_progress
    cancelled: desde received, assessing, resources_assigned o in_progress.

Transiciones automáticas (asignación de recursos, Fase 4):

    received / assessing  → resources_assigned   al asignar el primer recurso
    resources_assigned    → assessing            al retirar el último

`resources_assigned` nunca es una acción manual: solo se alcanza asignando.
"""

from collections.abc import Iterable, Mapping

from app.domain.enums import IncidentPriority, IncidentStatus

S = IncidentStatus

ALLOWED_TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    S.RECEIVED: frozenset({S.ASSESSING, S.CANCELLED}),
    S.ASSESSING: frozenset({S.IN_PROGRESS, S.CANCELLED}),
    S.RESOURCES_ASSIGNED: frozenset({S.IN_PROGRESS, S.CANCELLED}),
    S.IN_PROGRESS: frozenset({S.CONTROLLED, S.CANCELLED}),
    S.CONTROLLED: frozenset({S.CLOSED, S.IN_PROGRESS}),
    S.CLOSED: frozenset(),
    S.CANCELLED: frozenset(),
}

# Transiciones automáticas por la asignación de recursos.
_ASSIGNABLE_FROM: frozenset[IncidentStatus] = frozenset({S.RECEIVED, S.ASSESSING})
AUTOMATIC_TRANSITIONS: dict[IncidentStatus, frozenset[IncidentStatus]] = {
    S.RECEIVED: frozenset({S.RESOURCES_ASSIGNED}),
    S.ASSESSING: frozenset({S.RESOURCES_ASSIGNED}),
    S.RESOURCES_ASSIGNED: frozenset({S.ASSESSING}),
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


def status_after_assignment(current: IncidentStatus) -> IncidentStatus:
    """Estado tras asignar un recurso: el primero lleva a `resources_assigned`
    si el incidente aún no estaba en intervención."""
    return S.RESOURCES_ASSIGNED if current in _ASSIGNABLE_FROM else current


def status_after_last_release(current: IncidentStatus) -> IncidentStatus:
    """Estado tras retirar el último recurso activo: si seguía esperando a los
    recursos, vuelve a valoración; en intervención o controlado, no cambia."""
    return S.ASSESSING if current == S.RESOURCES_ASSIGNED else current


def allowed_transitions(current: IncidentStatus) -> list[IncidentStatus]:
    """Estados de destino válidos, en el orden del enum (estable para la UI)."""
    return [status for status in IncidentStatus if status in ALLOWED_TRANSITIONS[current]]


def is_active(status: IncidentStatus) -> bool:
    return status in ACTIVE_STATUSES


def reachable_statuses() -> frozenset[IncidentStatus]:
    """Estados alcanzables desde el inicial, con transiciones manuales y automáticas."""
    seen = {INITIAL_STATUS}
    pending = [INITIAL_STATUS]
    while pending:
        current = pending.pop()
        for target in ALLOWED_TRANSITIONS[current] | AUTOMATIC_TRANSITIONS.get(
            current, frozenset()
        ):
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return frozenset(seen)


# --- Edición operativa (CLAUDE.md §2.11, D6) ------------------------------------

# Campos que puede modificar quien solo tiene la edición operativa. El resto
# (prioridad, título, incidente padre…) exige la edición completa. El tipo no
# se puede cambiar nunca.
OPERATIONAL_FIELDS: frozenset[str] = frozenset(
    {"description", "affected_people", "location", "details"}
)


def fields_requiring_full_edit(sent: Iterable[str]) -> frozenset[str]:
    """Campos enviados en una edición que quedan fuera de la edición operativa.

    Cuenta lo **enviado**, no lo que cambiaría: una petición que incluye un
    campo no permitido se rechaza entera aunque su valor coincida con el actual.
    """
    return frozenset(sent) - OPERATIONAL_FIELDS


# Campos del alta que solo puede indicar quien tiene la edición completa
# (CLAUDE.md §2.11, D10 y D11). Sin ella, se aplican sus valores por defecto:
# la prioridad del tipo y ningún incidente padre.
CREATE_FIELDS_REQUIRING_FULL_EDIT: frozenset[str] = frozenset({"priority", "parent_incident_id"})


def create_fields_requiring_full_edit(values: Mapping[str, object]) -> frozenset[str]:
    """Campos del alta con valor (distinto de `None`) que exigen la edición completa."""
    return frozenset(
        name for name in CREATE_FIELDS_REQUIRING_FULL_EDIT if values.get(name) is not None
    )
