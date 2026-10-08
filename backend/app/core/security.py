"""Primitivas criptográficas: contraseñas, access tokens y refresh tokens.

Funciones puras sin acceso a base de datos ni HTTP. Nunca registran ni
devuelven contraseñas o tokens en mensajes de error.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from app.domain.exceptions import AuthenticationError

# --- Contraseñas (Argon2) ----------------------------------------------------

_password_hash = PasswordHash((Argon2Hasher(),))

# Hash de una contraseña aleatoria que nadie conoce. Se verifica contra él
# cuando el email no existe, para que la respuesta tarde lo mismo y no revele
# qué emails están registrados.
_DUMMY_PASSWORD_HASH = _password_hash.hash(secrets.token_urlsafe(32))


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> tuple[bool, str | None]:
    """Devuelve (válida, nuevo_hash). `nuevo_hash` no es None si los parámetros
    de Argon2 han cambiado y conviene guardar el hash actualizado."""
    if password_hash is None:
        _password_hash.verify(password, _DUMMY_PASSWORD_HASH)
        return False, None
    return _password_hash.verify_and_update(password, password_hash)


# --- Access token (JWT de corta duración) -----------------------------------

JWT_ISSUER = "emergency-command"
JWT_AUDIENCE = "emergency-command-api"
_ACCESS_TOKEN_TYPE = "access"  # noqa: S105 — tipo de token, no un secreto
# Tolerancia ante pequeñas diferencias de reloj.
_JWT_LEEWAY = timedelta(seconds=10)


@dataclass(frozen=True, slots=True)
class AccessToken:
    token: str
    expires_at: datetime


def create_access_token(
    user_id: uuid.UUID,
    *,
    secret_key: str,
    algorithm: str,
    now: datetime,
    lifetime: timedelta,
) -> AccessToken:
    expires_at = now + lifetime
    claims = {
        "sub": str(user_id),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": expires_at,
        "jti": uuid.uuid4().hex,
        "typ": _ACCESS_TOKEN_TYPE,
    }
    return AccessToken(jwt.encode(claims, secret_key, algorithm=algorithm), expires_at)


def decode_access_token(token: str, *, secret_key: str, algorithm: str) -> uuid.UUID:
    """Devuelve el id de usuario del token o lanza AuthenticationError."""
    try:
        claims = jwt.decode(
            token,
            secret_key,
            algorithms=[algorithm],
            audience=JWT_AUDIENCE,
            issuer=JWT_ISSUER,
            leeway=_JWT_LEEWAY,
            options={"require": ["sub", "exp", "iat", "iss", "aud", "typ"]},
        )
        if claims["typ"] != _ACCESS_TOKEN_TYPE:
            raise AuthenticationError("invalid_token")
        return uuid.UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError) as exc:
        raise AuthenticationError("invalid_token") from exc


# --- Refresh token (opaco, rotado, guardado como hash) ----------------------


def generate_refresh_token() -> str:
    # 32 bytes = 256 bits de entropía.
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    # SHA-256 basta: el token es aleatorio de 256 bits, no una contraseña.
    return hashlib.sha256(token.encode()).hexdigest()
