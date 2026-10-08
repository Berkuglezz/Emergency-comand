import pytest

from app.domain.enums import ResourceStatus
from app.domain.resource_rules import INITIAL_STATUS, STATUS_RANK, can_change_status


@pytest.mark.parametrize("current", list(ResourceStatus))
@pytest.mark.parametrize("target", list(ResourceStatus))
def test_any_status_change_except_to_itself(
    current: ResourceStatus, target: ResourceStatus
) -> None:
    assert can_change_status(current, target) is (current != target)


def test_new_resources_start_available() -> None:
    assert INITIAL_STATUS is ResourceStatus.AVAILABLE


def test_every_status_has_a_distinct_rank() -> None:
    assert set(STATUS_RANK) == set(ResourceStatus)
    assert len(set(STATUS_RANK.values())) == len(ResourceStatus)
    assert min(STATUS_RANK, key=STATUS_RANK.__getitem__) is ResourceStatus.AVAILABLE
