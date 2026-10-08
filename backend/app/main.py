"""Punto de entrada de la API."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.errors import register_exception_handlers
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # La documentación interactiva y el esquema OpenAPI solo existen en desarrollo.
    docs_enabled = settings.is_development
    app = FastAPI(
        title="Emergency Command API",
        summary="Prototipo de demostración. No es un sistema real de emergencias.",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )
    register_exception_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
