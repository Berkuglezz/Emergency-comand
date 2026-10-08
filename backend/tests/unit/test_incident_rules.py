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
)

S = IncidentStatus

# Flujo aprobado para la Fase 2 (CLAUDE.md §2.3 y decisión 4).
EXPECTED_TRANSITIONS = {
    (S.RECEIVED, S.ASSESSING),
    (S.ASSESSING, S.IN_PROGRESS),
    (S.IN_PROGRESS, S.CONTROLLED),
    (S.CONTROLLED, S.CLOSED),
    (S.CONTROLLED, S.IN_PROGRESS),  # reapertura
    (S.RECEIVED, S.CANCELLED),
    (S.ASSESSING, S.CANCELLED),
    (S.IN_PROGRESS, S.CANCELLED),
}


@pytest.mark.parametrize("current", list(IncidentStatus))
@pytest.mark.parametrize("target", list(IncidentStatus))
def test_only_approved_transitions_are_allowed(current: S, target: S) -> None:
    assert can_transition(current, target) is ((current, target) in EXPECTED_TRANSITIONS)


def test_flow_starts_at_received_and_must_pass_through_assessing() -> None:
    assert INITIAL_STATUS is S.RECEIVED
    assert not can_transition(S.RECEIVED, S.IN_PROGRESS)


def test_resources_assigned_is_not_reachable_in_phase_2() -> None:
    assert S.RESOURCES_ASSIGNED not in reachable_statuses()
    assert reachable_statuses() == frozenset(IncidentStatus) - {S.RESOURCES_ASSIGNED}


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
