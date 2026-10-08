from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

from app.api.v1.deps import get_health_service
from app.core.config import get_settings
from app.main import create_app
from app.services.health import HealthService


async def test_health_ok_with_database(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


class _UnavailableDatabase:
    async def ping(self) -> None:
        raise OperationalError("SELECT 1", {}, ConnectionRefusedError())


async def test_health_degraded_without_database(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_health_service] = lambda: HealthService(_UnavailableDatabase())

    response = await client.get("/api/v1/health")

    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "database": "unavailable"}


async def test_openapi_docs_available_in_development() -> None:
    settings = get_settings().model_copy(update={"environment": "development"})
    transport = ASGITransport(app=create_app(settings))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/docs")).status_code == 200
        assert (await client.get("/openapi.json")).status_code == 200
