"""Login, refresh con rotación, logout y /me a través de la API."""

from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH
from app.core.config import get_settings
from app.core.security import create_access_token, hash_refresh_token
from app.domain.enums import RoleCode
from app.models import RefreshToken, User
from tests.conftest import TEST_PASSWORD, UserFactory

pytestmark = pytest.mark.usefixtures("db_connection")


def _refresh_cookie(response: Response) -> SimpleCookie:
    cookie: SimpleCookie = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        cookie.load(header)
    return cookie


def _refresh_token_from(response: Response) -> str:
    return _refresh_cookie(response)[REFRESH_COOKIE_NAME].value


async def _login(client: AsyncClient, email: str, password: str = TEST_PASSWORD) -> Response:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    # Las cookies se envían a mano en cada test: así se controla qué token se usa.
    client.cookies.clear()
    return response


async def _refresh(client: AsyncClient, token: str | None) -> Response:
    headers = {"Cookie": f"{REFRESH_COOKIE_NAME}={token}"} if token else {}
    response = await client.post("/api/v1/auth/refresh", headers=headers)
    client.cookies.clear()
    return response


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _stored(session: AsyncSession, raw_token: str) -> RefreshToken:
    # populate_existing: lee el estado actual de la fila aunque ya esté en la sesión.
    return (
        await session.scalars(
            select(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(raw_token))
            .execution_options(populate_existing=True)
        )
    ).one()


# --- Login ------------------------------------------------------------------


async def test_login_returns_access_token_and_refresh_cookie(
    client: AsyncClient, make_user: UserFactory
) -> None:
    user = await make_user(RoleCode.OPERATOR)

    response = await _login(client, user.email)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == get_settings().access_token_expire_minutes * 60
    assert set(body) == {"access_token", "token_type", "expires_in"}

    morsel = _refresh_cookie(response)[REFRESH_COOKIE_NAME]
    assert morsel["httponly"] is True
    assert morsel["samesite"].lower() == "lax"
    assert morsel["path"] == REFRESH_COOKIE_PATH
    assert bool(morsel["secure"]) is get_settings().refresh_cookie_secure
    assert morsel.value not in response.text


async def test_login_is_case_insensitive_for_email(
    client: AsyncClient, make_user: UserFactory
) -> None:
    await make_user(RoleCode.OPERATOR, email="mixed@example.test")
    response = await _login(client, "  MIXED@Example.TEST ")
    assert response.status_code == 200


async def test_login_records_last_login(
    client: AsyncClient, make_user: UserFactory, session: AsyncSession
) -> None:
    user = await make_user(RoleCode.OPERATOR)
    await _login(client, user.email)
    await session.refresh(user)
    assert user.last_login_at is not None


@pytest.mark.parametrize(
    ("email", "password"),
    [
        ("operator@example.test", "wrong-password"),
        ("nobody@example.test", TEST_PASSWORD),
    ],
)
async def test_login_with_bad_credentials_fails_without_detail(
    client: AsyncClient, make_user: UserFactory, email: str, password: str
) -> None:
    await make_user(RoleCode.OPERATOR)

    response = await _login(client, email, password)

    # Mismo código para email inexistente y contraseña incorrecta.
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_credentials"}
    assert REFRESH_COOKIE_NAME not in response.headers.get("set-cookie", "")


async def test_inactive_user_cannot_log_in(client: AsyncClient, make_user: UserFactory) -> None:
    user = await make_user(RoleCode.OPERATOR, is_active=False)
    response = await _login(client, user.email)
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_credentials"}


async def test_login_validates_payload(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": "a@b.c"})
    assert response.status_code == 422


# --- /me y access token --------------------------------------------------------


async def test_me_returns_profile_role_and_permissions(
    client: AsyncClient, make_user: UserFactory
) -> None:
    user = await make_user(RoleCode.COORDINATOR, with_organization=True)
    access = (await _login(client, user.email)).json()["access_token"]

    response = await client.get("/api/v1/auth/me", headers=_bearer(access))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    assert body["role"] == "coordinator"
    assert body["permissions"] == [
        "assignments:manage",
        "assignments:update",
        "incidents:close",
        "incidents:create",
        "incidents:read",
        "incidents:update",
        "organizations:read",
        "resources:read",
        "resources:update_status",
    ]
    assert body["organization"]["code"] == "test-coordinator"
    assert "password_hash" not in body
    assert "password" not in response.text


@pytest.mark.parametrize(
    ("headers", "code"),
    [
        ({}, "not_authenticated"),
        ({"Authorization": "Bearer not-a-jwt"}, "invalid_token"),
        ({"Authorization": "Basic dXNlcjpwYXNz"}, "not_authenticated"),
    ],
)
async def test_me_requires_a_valid_access_token(
    client: AsyncClient, headers: dict[str, str], code: str
) -> None:
    response = await client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert response.json() == {"detail": code}
    assert response.headers["www-authenticate"] == "Bearer"


async def test_expired_access_token_is_rejected(
    client: AsyncClient, make_user: UserFactory
) -> None:
    user = await make_user(RoleCode.OPERATOR)
    settings = get_settings()
    expired = create_access_token(
        user.id,
        secret_key=settings.jwt_secret_key.get_secret_value(),
        algorithm=settings.jwt_algorithm,
        now=datetime.now(UTC) - timedelta(hours=1),
        lifetime=timedelta(minutes=15),
    ).token

    response = await client.get("/api/v1/auth/me", headers=_bearer(expired))

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_token"}


async def test_deactivated_user_loses_access_immediately(
    client: AsyncClient, make_user: UserFactory, session: AsyncSession
) -> None:
    user = await make_user(RoleCode.OPERATOR)
    access = (await _login(client, user.email)).json()["access_token"]

    await session.execute(update(User).where(User.id == user.id).values(is_active=False))
    await session.commit()

    response = await client.get("/api/v1/auth/me", headers=_bearer(access))
    assert response.status_code == 401


# --- Refresh con rotación ---------------------------------------------------


async def test_refresh_rotates_the_token(
    client: AsyncClient, make_user: UserFactory, session: AsyncSession
) -> None:
    user = await make_user(RoleCode.OPERATOR)
    first = _refresh_token_from(await _login(client, user.email))

    response = await _refresh(client, first)

    assert response.status_code == 200
    second = _refresh_token_from(response)
    assert second != first

    old, new = await _stored(session, first), await _stored(session, second)
    assert old.revoked_at is not None
    assert old.replaced_by_id == new.id
    assert new.family_id == old.family_id
    assert new.revoked_at is None

    me = await client.get("/api/v1/auth/me", headers=_bearer(response.json()["access_token"]))
    assert me.status_code == 200


async def test_refresh_without_cookie_fails(client: AsyncClient) -> None:
    response = await _refresh(client, None)
    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_refresh_token"}


async def test_refresh_with_unknown_token_fails_and_clears_cookie(client: AsyncClient) -> None:
    response = await _refresh(client, "unknown-token")

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_refresh_token"}
    # Cookie borrada: valor vacío y caducada.
    assert _refresh_cookie(response)[REFRESH_COOKIE_NAME].value == ""


async def test_expired_refresh_token_fails(
    client: AsyncClient, make_user: UserFactory, session: AsyncSession
) -> None:
    user = await make_user(RoleCode.OPERATOR)
    token = _refresh_token_from(await _login(client, user.email))
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(token))
        .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    )
    await session.commit()

    response = await _refresh(client, token)

    assert response.status_code == 401
    assert response.json() == {"detail": "invalid_refresh_token"}


async def test_reusing_a_rotated_token_revokes_the_whole_session(
    client: AsyncClient, make_user: UserFactory, session: AsyncSession
) -> None:
    user = await make_user(RoleCode.OPERATOR)
    first = _refresh_token_from(await _login(client, user.email))
    second = _refresh_token_from(await _refresh(client, first))

    # Fuera del margen de gracia: el token rotado se usó hace un minuto.
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(first))
        .values(revoked_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await session.commit()

    reuse = await _refresh(client, first)
    assert reuse.status_code == 401
    assert reuse.json() == {"detail": "refresh_token_reused"}

    # El token legítimo más reciente también queda invalidado.
    assert (await _stored(session, second)).revoked_at is not None
    after = await _refresh(client, second)
    assert after.status_code == 401
    assert after.json() == {"detail": "refresh_token_reused"}


async def test_concurrent_refresh_within_grace_keeps_the_session(
    client: AsyncClient, make_user: UserFactory, session: AsyncSession
) -> None:
    user = await make_user(RoleCode.OPERATOR)
    first = _refresh_token_from(await _login(client, user.email))
    second = _refresh_token_from(await _refresh(client, first))

    # Otra pestaña presenta el mismo token justo después de la rotación.
    race = await _refresh(client, first)

    assert race.status_code == 401
    assert race.json() == {"detail": "refresh_token_rotated"}
    # No se borra la cookie (el navegador ya tiene la nueva) ni se revoca la sesión.
    assert REFRESH_COOKIE_NAME not in race.headers.get("set-cookie", "")
    assert (await _stored(session, second)).revoked_at is None
    assert (await _refresh(client, second)).status_code == 200


async def test_refresh_fails_for_deactivated_user(
    client: AsyncClient, make_user: UserFactory, session: AsyncSession
) -> None:
    user = await make_user(RoleCode.OPERATOR)
    token = _refresh_token_from(await _login(client, user.email))
    await session.execute(update(User).where(User.id == user.id).values(is_active=False))
    await session.commit()

    response = await _refresh(client, token)

    assert response.status_code == 401
    assert (await _stored(session, token)).revoked_at is not None


# --- Logout -----------------------------------------------------------------


async def test_logout_invalidates_the_session(client: AsyncClient, make_user: UserFactory) -> None:
    user = await make_user(RoleCode.OPERATOR)
    login = await _login(client, user.email)
    access, refresh_token = login.json()["access_token"], _refresh_token_from(login)

    response = await client.post(
        "/api/v1/auth/logout",
        headers={**_bearer(access), "Cookie": f"{REFRESH_COOKIE_NAME}={refresh_token}"},
    )
    client.cookies.clear()

    assert response.status_code == 204
    assert _refresh_cookie(response)[REFRESH_COOKIE_NAME].value == ""
    after = await _refresh(client, refresh_token)
    assert after.status_code == 401


async def test_logout_only_closes_the_current_session(
    client: AsyncClient, make_user: UserFactory
) -> None:
    user = await make_user(RoleCode.OPERATOR)
    laptop = await _login(client, user.email)
    tablet_token = _refresh_token_from(await _login(client, user.email))

    await client.post(
        "/api/v1/auth/logout",
        headers={
            **_bearer(laptop.json()["access_token"]),
            "Cookie": f"{REFRESH_COOKIE_NAME}={_refresh_token_from(laptop)}",
        },
    )
    client.cookies.clear()

    assert (await _refresh(client, tablet_token)).status_code == 200


async def test_logout_cannot_revoke_another_users_session(
    client: AsyncClient, make_user: UserFactory
) -> None:
    victim = await make_user(RoleCode.OPERATOR)
    attacker = await make_user(RoleCode.OPERATOR, email="attacker@example.test")
    victim_token = _refresh_token_from(await _login(client, victim.email))
    attacker_access = (await _login(client, attacker.email)).json()["access_token"]

    await client.post(
        "/api/v1/auth/logout",
        headers={**_bearer(attacker_access), "Cookie": f"{REFRESH_COOKIE_NAME}={victim_token}"},
    )
    client.cookies.clear()

    assert (await _refresh(client, victim_token)).status_code == 200


async def test_logout_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 401
