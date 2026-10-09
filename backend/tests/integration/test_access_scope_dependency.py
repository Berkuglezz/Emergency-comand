"""`get_access_scope` con usuarios reales de cada rol (CLAUDE.md §2.11, R.3).

En R.3 ninguna ruta usa todavía el ámbito; aquí se prueba la dependencia
directamente, a partir del usuario autenticado tal como lo carga el backend.
"""

import uuid

import pytest

from app.api.v1.deps import get_access_scope
from app.domain.enums import RoleCode
from tests.conftest import UserFactory

OTHER = uuid.uuid4()


@pytest.mark.parametrize("role", [RoleCode.ADMIN, RoleCode.COORDINATOR])
async def test_admin_and_coordinator_scope(make_user: UserFactory, role: RoleCode) -> None:
    user = await make_user(role, with_organization=True)
    scope = get_access_scope(user)
    assert user.organization_id is not None
    assert scope.can_write(user.organization_id)
    assert scope.can_write(OTHER)
    assert scope.can_read(OTHER)


async def test_operator_scope_is_its_organization(make_user: UserFactory) -> None:
    user = await make_user(RoleCode.OPERATOR, with_organization=True)
    scope = get_access_scope(user)
    assert user.organization_id is not None
    assert scope.can_write(user.organization_id)
    assert not scope.can_write(OTHER)
    assert scope.can_read(OTHER)


async def test_operator_without_organization_cannot_write(make_user: UserFactory) -> None:
    user = await make_user(RoleCode.OPERATOR)
    assert user.organization_id is None
    scope = get_access_scope(user)
    assert not scope.can_write(OTHER)
    assert scope.can_read(OTHER)
