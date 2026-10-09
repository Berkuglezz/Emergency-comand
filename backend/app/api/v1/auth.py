"""Endpoints de autenticación.

- El access token se devuelve en el cuerpo y el cliente lo guarda en memoria.
- El refresh token viaja solo en una cookie httpOnly limitada a /api/v1/auth.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Response, status
from fastapi.responses import JSONResponse

from app.api.errors import domain_error_response
from app.api.v1.deps import AccessScopeDep, AuthServiceDep, CurrentUserDep, SettingsDep
from app.core.config import Settings
from app.core.permissions import permissions_for
from app.domain.exceptions import AuthenticationError
from app.schemas.auth import AccessScopeResponse, LoginRequest, MeResponse, TokenResponse
from app.schemas.errors import ErrorResponse
from app.schemas.organizations import OrganizationSummary
from app.services.auth import IssuedTokens

REFRESH_COOKIE_NAME = "ec_refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"

RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)]

_UNAUTHORIZED: dict[int | str, dict[str, Any]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}
}

public_router = APIRouter(prefix="/auth", tags=["auth"])
protected_router = APIRouter(prefix="/auth", tags=["auth"], responses=_UNAUTHORIZED)


def _set_refresh_cookie(response: Response, tokens: IssuedTokens, settings: Settings) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=tokens.refresh_token,
        expires=tokens.refresh_expires_at,
        path=REFRESH_COOKIE_PATH,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=settings.refresh_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _token_response(tokens: IssuedTokens) -> TokenResponse:
    return TokenResponse(access_token=tokens.access_token, expires_in=tokens.access_expires_in)


@public_router.post("/login", responses=_UNAUTHORIZED)
async def login(
    body: LoginRequest, response: Response, auth: AuthServiceDep, settings: SettingsDep
) -> TokenResponse:
    tokens = await auth.login(body.email, body.password)
    _set_refresh_cookie(response, tokens, settings)
    return _token_response(tokens)


@public_router.post("/refresh", response_model=TokenResponse, responses=_UNAUTHORIZED)
async def refresh(
    response: Response,
    auth: AuthServiceDep,
    settings: SettingsDep,
    refresh_token: RefreshCookie = None,
) -> TokenResponse | JSONResponse:
    try:
        tokens = await auth.refresh(refresh_token)
    except AuthenticationError as exc:
        error = domain_error_response(exc)
        # Tras una rotación concurrente la cookie del cliente ya es la nueva:
        # se conserva. En cualquier otro fallo se borra la cookie inválida.
        if exc.code != "refresh_token_rotated":
            _clear_refresh_cookie(error, settings)
        return error
    _set_refresh_cookie(response, tokens, settings)
    return _token_response(tokens)


@protected_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    user: CurrentUserDep,
    auth: AuthServiceDep,
    settings: SettingsDep,
    refresh_token: RefreshCookie = None,
) -> None:
    await auth.logout(refresh_token, user.id)
    _clear_refresh_cookie(response, settings)


@protected_router.get("/me")
async def me(user: CurrentUserDep, scope: AccessScopeDep) -> MeResponse:
    """Perfil, permisos y ámbito organizativo efectivos del usuario autenticado."""
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.code,
        permissions=sorted(permissions_for(user.role.code)),
        organization=(
            OrganizationSummary.model_validate(user.organization) if user.organization else None
        ),
        scope=AccessScopeResponse.from_domain(scope),
    )
