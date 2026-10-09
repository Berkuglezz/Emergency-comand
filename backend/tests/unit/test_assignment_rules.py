"""Reglas puras de asignación (`app.domain.assignment_rules`)."""

import pytest

from app.domain.assignment_rules import (
    USER_RELEASE_REASONS,
    assignment_blocker,
    resource_status_after_release,
)
from app.domain.enums import ReleaseReason, ResourceStatus


@pytest.mark.parametrize(
    ("is_active", "status", "code"),
    [
        (True, ResourceStatus.AVAILABLE, None),
        (True, ResourceStatus.IN_SERVICE, "resource_not_available"),
        (True, ResourceStatus.OUT_OF_SERVICE, "resource_not_available"),
        (False, ResourceStatus.AVAILABLE, "resource_inactive"),
    ],
)
def test_only_active_and_available_resources_can_be_assigned(
    is_active: bool, status: ResourceStatus, code: str | None
) -> None:
    assert assignment_blocker(is_active=is_active, status=status) == code


@pytest.mark.parametrize(
    ("reason", "status"),
    [
        (ReleaseReason.COMPLETED, ResourceStatus.AVAILABLE),
        (ReleaseReason.NOT_NEEDED, ResourceStatus.AVAILABLE),
        (ReleaseReason.REASSIGNED, ResourceStatus.AVAILABLE),
        (ReleaseReason.INCIDENT_CLOSED, ResourceStatus.AVAILABLE),
        (ReleaseReason.UNAVAILABLE, ResourceStatus.OUT_OF_SERVICE),
    ],
)
def test_resource_status_after_release(reason: ReleaseReason, status: ResourceStatus) -> None:
    assert resource_status_after_release(reason) is status


def test_system_reasons_cannot_be_chosen_by_a_person() -> None:
    assert ReleaseReason.REASSIGNED not in USER_RELEASE_REASONS
    assert ReleaseReason.INCIDENT_CLOSED not in USER_RELEASE_REASONS
