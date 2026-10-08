from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from app.core.config import Settings
from app.main import create_app


async def test_docs_disabled_outside_development() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        postgres_user="user",
        postgres_password=SecretStr("a-real-password"),
        postgres_db="db",
        jwt_secret_key=SecretStr("x" * 64),
        refresh_cookie_secure=True,
    )
    app = create_app(settings)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/docs")).status_code == 404
        assert (await client.get("/openapi.json")).status_code == 404
