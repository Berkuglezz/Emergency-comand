import pytest

from app.domain.enums import IncidentPriority, IncidentStatus
from app.domain.incident_rules import (
    ACTIVE_STATUSES,
    ALLOWED_TRANSITIONS,
    CLOSING_STATUSES,
    INITIAL_STATUS,
    PRIORITY_RANK,
    allowed_transitions,
    can_transition,
    is_active,
    reachable_statuses,
    status_after_assignment,
    status_after_last_release,
)

S = IncidentStatus

# Flujo manual aprobado (CLAUDE.md §2.3 y §2.8).
EXPECTED_TRANSITIONS = {
    (S.RECEIVED, S.ASSESSING),
    (S.ASSESSING, S.IN_PROGRESS),
    (S.IN_PROGRESS, S.CONTROLLED),
    (S.CONTROLLED, S.CLOSED),
    (S.CONTROLLED, S.IN_PROGRESS),  # reapertura
    (S.RECEIVED, S.CANCELLED),
    (S.ASSESSING, S.CANCELLED),
    (S.IN_PROGRESS, S.CANCELLED),
    # Fase 4: desde `resources_assigned` (al que solo se llega asignando).
    (S.RESOURCES_ASSIGNED, S.IN_PROGRESS),
    (S.RESOURCES_ASSIGNED, S.CANCELLED),
}


@pytest.mark.parametrize("current", list(IncidentStatus))
@pytest.mark.parametrize("target", list(IncidentStatus))
def test_only_approved_transitions_are_allowed(current: S, target: S) -> None:
    assert can_transition(current, target) is ((current, target) in EXPECTED_TRANSITIONS)


def test_flow_starts_at_received_and_must_pass_through_assessing() -> None:
    assert INITIAL_STATUS is S.RECEIVED
    assert not can_transition(S.RECEIVED, S.IN_PROGRESS)


def test_resources_assigned_is_never_a_manual_target() -> None:
    assert not any(can_transition(current, S.RESOURCES_ASSIGNED) for current in IncidentStatus)
    # …pero se alcanza automáticamente al asignar recursos.
    assert reachable_statuses() == frozenset(IncidentStatus)


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (S.RECEIVED, S.RESOURCES_ASSIGNED),
        (S.ASSESSING, S.RESOURCES_ASSIGNED),
        (S.RESOURCES_ASSIGNED, S.RESOURCES_ASSIGNED),
        (S.IN_PROGRESS, S.IN_PROGRESS),
        (S.CONTROLLED, S.CONTROLLED),
    ],
)
def test_status_after_assignment(current: S, expected: S) -> None:
    assert status_after_assignment(current) is expected


@pytest.mark.parametrize(
    ("current", "expected"),
    [
        (S.RESOURCES_ASSIGNED, S.ASSESSING),
        (S.IN_PROGRESS, S.IN_PROGRESS),
        (S.CONTROLLED, S.CONTROLLED),
    ],
)
def test_status_after_last_release(current: S, expected: S) -> None:
    assert status_after_last_release(current) is expected


def test_controlled_cannot_be_cancelled() -> None:
    assert not can_transition(S.CONTROLLED, S.CANCELLED)


@pytest.mark.parametrize("terminal", [S.CLOSED, S.CANCELLED])
def test_terminal_statuses_have_no_exit(terminal: S) -> None:
    assert not any(can_transition(terminal, target) for target in IncidentStatus)
    assert not is_active(terminal)


def test_active_and_closing_statuses() -> None:
    assert frozenset({S.CLOSED, S.CANCELLED}) == CLOSING_STATUSES
    assert frozenset(IncidentStatus) - CLOSING_STATUSES == ACTIVE_STATUSES


def test_priority_rank_orders_by_urgency() -> None:
    ordered = sorted(IncidentPriority, key=PRIORITY_RANK.__getitem__)
    assert ordered == [
        IncidentPriority.CRITICAL,
        IncidentPriority.HIGH,
        IncidentPriority.MEDIUM,
        IncidentPriority.LOW,
    ]


@pytest.mark.parametrize("current", list(IncidentStatus))
def test_allowed_transitions_match_the_rules_in_enum_order(current: S) -> None:
    targets = allowed_transitions(current)
    assert set(targets) == ALLOWED_TRANSITIONS[current]
    assert targets == sorted(targets, key=list(IncidentStatus).index)
