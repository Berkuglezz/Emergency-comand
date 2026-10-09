"""Ámbito organizativo (CLAUDE.md §2.11, R.3): reglas puras por rol."""

import dataclasses
import uuid
from typing import cast

import pytest

from app.domain.access_scope import SCOPE_RULES, AccessScope, OrganizationAccess, scope_for
from app.domain.enums import RoleCode
from app.domain.exceptions import NotFoundError, OutOfScopeError, PermissionDeniedError

OWN = uuid.uuid4()
OTHER = uuid.uuid4()


def test_every_role_has_an_explicit_rule() -> None:
    # Un rol nuevo sin regla de ámbito hace fallar este test.
    assert set(SCOPE_RULES) == set(RoleCode)


@pytest.mark.parametrize("role", [RoleCode.ADMIN, RoleCode.COORDINATOR])
@pytest.mark.parametrize("organization_id", [OWN, None])
def test_admin_and_coordinator_reach_every_organization(
    role: RoleCode, organization_id: uuid.UUID | None
) -> None:
    scope = scope_for(role, organization_id)
    for organization in (OWN, OTHER):
        assert scope.can_read(organization)
        assert scope.can_write(organization)


def test_operator_reads_everything_but_writes_only_its_organization() -> None:
    scope = scope_for(RoleCode.OPERATOR, OWN)
    assert scope.can_read(OWN)
    assert scope.can_read(OTHER)
    assert scope.can_write(OWN)
    assert not scope.can_write(OTHER)


def test_operator_without_organization_cannot_write() -> None:
    scope = scope_for(RoleCode.OPERATOR, None)
    assert scope.can_read(OWN)
    assert not scope.can_write(OWN)
    assert not scope.can_write(OTHER)
    assert scope.write == OrganizationAccess.nothing()


def test_unknown_role_fails_closed() -> None:
    with pytest.raises(PermissionDeniedError):
        scope_for(cast(RoleCode, "auditor"), OWN)


def test_organization_access() -> None:
    assert OrganizationAccess.everything().allows(OTHER)
    assert not OrganizationAccess.nothing().allows(OWN)
    only = OrganizationAccess.only(OWN)
    assert only.allows(OWN)
    assert not only.allows(OTHER)


def test_scope_is_immutable() -> None:
    scope = scope_for(RoleCode.OPERATOR, OWN)
    with pytest.raises(dataclasses.FrozenInstanceError):
        scope.write = OrganizationAccess.everything()  # type: ignore[misc]  # se comprueba que falla
    with pytest.raises(AttributeError):
        scope.write.organization_ids.add(OTHER)  # type: ignore[attr-defined]  # frozenset
    assert isinstance(scope, AccessScope)


@pytest.mark.parametrize("role", list(RoleCode))
@pytest.mark.parametrize("organization_id", [OWN, None])
def test_write_scope_never_limits_reading(
    role: RoleCode, organization_id: uuid.UUID | None
) -> None:
    """D4: todos los roles leen todas las organizaciones, tengan o no
    organización y sea cual sea su ámbito de escritura."""
    scope = scope_for(role, organization_id)
    assert scope.read == OrganizationAccess.everything()
    for organization in (OWN, OTHER):
        scope.require_read(organization, not_found="resource_not_found")


def test_require_read_hides_out_of_scope_as_not_found() -> None:
    scope = AccessScope(read=OrganizationAccess.only(OWN), write=OrganizationAccess.nothing())
    scope.require_read(OWN, not_found="resource_not_found")
    with pytest.raises(NotFoundError) as raised:
        scope.require_read(OTHER, not_found="resource_not_found")
    assert raised.value.code == "resource_not_found"


def test_require_write() -> None:
    scope = scope_for(RoleCode.OPERATOR, OWN)
    scope.require_write(OWN)
    with pytest.raises(OutOfScopeError):
        scope.require_write(OTHER)


def test_as_filter() -> None:
    assert OrganizationAccess.everything().as_filter() is None
    assert OrganizationAccess.nothing().as_filter() == frozenset()
    assert OrganizationAccess.only(OWN).as_filter() == frozenset({OWN})
