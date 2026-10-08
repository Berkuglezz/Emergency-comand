"""Autorización por rol y protección por defecto de los endpoints."""

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.domain.enums import RoleCode
from tests.conftest import TEST_PASSWORD, UserFactory

PUBLIC_ROUTES = {
    ("GET", "/api/v1/health"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
}


async def _access_token(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": TEST_PASSWORD}
    )
    client.cookies.clear()
    token: str = response.json()["access_token"]
    return token


@pytest.mark.parametrize(
    ("role", "status_code"),
    [(RoleCode.ADMIN, 200), (RoleCode.COORDINATOR, 200), (RoleCode.OPERATOR, 403)],
)
async def test_organizations_access_by_role(
    client: AsyncClient, make_user: UserFactory, role: RoleCode, status_code: int
) -> None:
    user = await make_user(role, with_organization=True)
    token = await _access_token(client, user.email)

    response = await client.get(
        "/api/v1/organizations", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == status_code
    if status_code == 403:
        assert response.json() == {"detail": "permission_denied"}
    else:
        codes = [org["code"] for org in response.json()]
        assert f"test-{role.value}" in codes


async def test_organizations_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/organizations")
    assert response.status_code == 401


async def test_every_non_public_route_requires_authentication(
    app: FastAPI, client: AsyncClient
) -> None:
    # El esquema OpenAPI es la lista pública de endpoints de la API.
    api_routes = [
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    ]
    assert set(api_routes) >= PUBLIC_ROUTES

    for method, path in api_routes:
        if (method, path) in PUBLIC_ROUTES:
            continue
        response = await client.request(method, path)
        assert response.status_code == 401, f"{method} {path} no está protegido"
