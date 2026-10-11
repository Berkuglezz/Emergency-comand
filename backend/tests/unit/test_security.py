import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.permissions import ROLE_PERMISSIONS, Permission, has_permission
from app.core.security import (
    JWT_AUDIENCE,
    JWT_ISSUER,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.domain.enums import RoleCode
from app.domain.exceptions import AuthenticationError

SECRET = "test-secret-key-with-enough-length-0123456789"
ALG = "HS256"


def _token(
    user_id: uuid.UUID, *, now: datetime | None = None, lifetime: timedelta | None = None
) -> str:
    return create_access_token(
        user_id,
        secret_key=SECRET,
        algorithm=ALG,
        now=now or datetime.now(UTC),
        lifetime=lifetime or timedelta(minutes=15),
    ).token


# --- Contraseñas -----------------------------------------------------------


def test_password_hash_is_argon2_and_verifies() -> None:
    hashed = hash_password("s3cret-pass")
    assert hashed.startswith("$argon2id$")
    assert "s3cret-pass" not in hashed
    assert verify_password("s3cret-pass", hashed)[0] is True
    assert verify_password("wrong", hashed)[0] is False


def test_verify_without_hash_is_always_false() -> None:
    assert verify_password("anything", None) == (False, None)


# --- Access token ---------------------------------------------------------


def test_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    assert decode_access_token(_token(user_id), secret_key=SECRET, algorithm=ALG) == user_id


def test_expired_access_token_is_rejected() -> None:
    token = _token(uuid.uuid4(), now=datetime.now(UTC) - timedelta(hours=1))
    with pytest.raises(AuthenticationError) as exc:
        decode_access_token(token, secret_key=SECRET, algorithm=ALG)
    assert exc.value.code == "invalid_token"


def test_access_token_with_other_key_is_rejected() -> None:
    with pytest.raises(AuthenticationError):
        decode_access_token(_token(uuid.uuid4()), secret_key="other-" + SECRET, algorithm=ALG)


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "other-audience"},
        {"iss": "other-issuer"},
        {"typ": "refresh"},
        {"sub": "not-a-uuid"},
    ],
)
def test_access_token_with_wrong_claims_is_rejected(claims: dict[str, str]) -> None:
    now = datetime.now(UTC)
    payload = {
        "sub": str(uuid.uuid4()),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "typ": "access",
        **claims,
    }
    token = jwt.encode(payload, SECRET, algorithm=ALG)
    with pytest.raises(AuthenticationError):
        decode_access_token(token, secret_key=SECRET, algorithm=ALG)


def test_unsigned_token_is_rejected() -> None:
    token = jwt.encode({"sub": str(uuid.uuid4())}, key=None, algorithm="none")
    with pytest.raises(AuthenticationError):
        decode_access_token(token, secret_key=SECRET, algorithm=ALG)


# --- Refresh token --------------------------------------------------------


def test_refresh_tokens_are_random_and_hashed() -> None:
    first, second = generate_refresh_token(), generate_refresh_token()
    assert first != second
    assert len(first) >= 43  # 32 bytes en base64url
    assert hash_refresh_token(first) == hash_refresh_token(first)
    assert len(hash_refresh_token(first)) == 64
    assert first not in hash_refresh_token(first)


# --- Permisos -------------------------------------------------------------


def test_every_role_has_a_permission_set() -> None:
    assert set(ROLE_PERMISSIONS) == set(RoleCode)


def test_admin_has_every_permission() -> None:
    assert ROLE_PERMISSIONS[RoleCode.ADMIN] == frozenset(Permission)


# Matriz aprobada para la Fase 2: (admin, coordinator, operator).
PERMISSION_MATRIX: dict[Permission, tuple[bool, bool, bool]] = {
    Permission.INCIDENTS_READ: (True, True, True),
    # Matriz aprobada en CLAUDE.md §2.11.2 (admin, coordinador, operador).
    Permission.INCIDENTS_CREATE: (True, True, True),
    Permission.INCIDENTS_UPDATE: (True, True, False),
    Permission.INCIDENTS_UPDATE_OPERATIONAL: (True, True, True),
    Permission.INCIDENTS_ANNOTATE: (True, True, True),
    Permission.INCIDENTS_CHANGE_STATUS: (True, True, False),
    Permission.INCIDENTS_CLOSE: (True, True, False),
    Permission.RESOURCES_READ: (True, True, True),
    Permission.RESOURCES_UPDATE_STATUS: (True, True, True),
    Permission.RESOURCES_MANAGE: (True, False, False),
    Permission.ORGANIZATIONS_READ: (True, True, False),
    Permission.ASSIGNMENTS_MANAGE: (True, True, False),
    Permission.ASSIGNMENTS_UPDATE: (True, True, True),
    # Mapa operativo (D-M2): solo coordinador y admin dibujan.
    Permission.MAP_FEATURES_MANAGE: (True, True, False),
}


def test_permission_matrix_covers_every_permission() -> None:
    assert set(PERMISSION_MATRIX) == set(Permission)


@pytest.mark.parametrize("permission", list(Permission))
@pytest.mark.parametrize(
    ("role", "column"), [(RoleCode.ADMIN, 0), (RoleCode.COORDINATOR, 1), (RoleCode.OPERATOR, 2)]
)
def test_permission_matrix(permission: Permission, role: RoleCode, column: int) -> None:
    assert has_permission(role, permission) is PERMISSION_MATRIX[permission][column]
