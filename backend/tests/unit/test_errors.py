import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
)


@pytest.mark.parametrize(
    ("error", "status_code", "code"),
    [
        (NotFoundError(), 404, "not_found"),
        (ConflictError("organization_exists"), 409, "organization_exists"),
        (AuthenticationError(), 401, "not_authenticated"),
        (PermissionDeniedError(), 403, "permission_denied"),
        (DomainError(), 400, "domain_error"),
    ],
)
async def test_domain_errors_are_translated_to_http(
    app: FastAPI, client: AsyncClient, error: DomainError, status_code: int, code: str
) -> None:
    @app.get("/_test/error")
    async def _raise() -> None:
        raise error

    response = await client.get("/_test/error")

    assert response.status_code == status_code
    assert response.json() == {"detail": code}


async def test_unhandled_errors_do_not_leak_details(app: FastAPI) -> None:
    @app.get("/_test/crash")
    async def _crash() -> None:
        raise RuntimeError("password=hunter2")

    # raise_app_exceptions=False: el cliente recibe la respuesta 500 en lugar
    # de propagar la excepción, igual que un cliente real.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/_test/crash")

    assert response.status_code == 500
    assert response.json() == {"detail": "internal_error"}
    assert "hunter2" not in response.text
