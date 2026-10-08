"""Traducción de excepciones de dominio a respuestas HTTP."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.domain.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    InvalidInputError,
    NotFoundError,
    PermissionDeniedError,
)
from app.schemas.errors import ErrorResponse

logger = logging.getLogger(__name__)

_STATUS_BY_ERROR: dict[type[DomainError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    InvalidInputError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def _status_for(exc: Exception) -> int:
    for error_type in type(exc).__mro__:
        if error_type in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[error_type]
    return status.HTTP_400_BAD_REQUEST


def domain_error_response(exc: DomainError) -> JSONResponse:
    status_code = _status_for(exc)
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(detail=exc.code).model_dump(),
        headers=headers,
    )


async def _domain_error_handler(_: Request, exc: Exception) -> JSONResponse:
    # Starlette tipa los manejadores con `Exception`; solo se registra para DomainError.
    return domain_error_response(exc if isinstance(exc, DomainError) else DomainError())


async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Se registra el tipo y la ruta, no el mensaje: podría contener datos sensibles.
    logger.error(
        "Error no controlado en %s %s: %s",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(detail="internal_error").model_dump(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, _domain_error_handler)
    app.add_exception_handler(Exception, _unhandled_error_handler)
