"""Autenticación: login, rotación de refresh tokens, logout y usuario actual."""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import NoReturn

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_password,
)
from app.domain.exceptions import AuthenticationError
from app.models import RefreshToken, User
from app.repositories.refresh_tokens import RefreshTokenRepository
from app.repositories.users import UserRepository

logger = logging.getLogger(__name__)

# Si un token recién rotado vuelve a presentarse dentro de este margen, se
# asume una carrera benigna (dos pestañas refrescando a la vez) y se rechaza
# con `refresh_token_rotated` sin revocar la sesión. Fuera del margen se trata
# como reutilización y se revoca toda la familia.
REFRESH_REUSE_GRACE = timedelta(seconds=10)


@dataclass(frozen=True, slots=True)
class IssuedTokens:
    access_token: str
    access_expires_in: int
    refresh_token: str
    refresh_expires_at: datetime


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)
        self._refresh_tokens = RefreshTokenRepository(session)

    async def login(self, email: str, password: str) -> IssuedTokens:
        user = await self._users.get_by_email(email)
        valid, updated_hash = verify_password(password, user.password_hash if user else None)
        if user is None or not valid or not user.is_active:
            raise AuthenticationError("invalid_credentials")

        now = self._now()
        if updated_hash is not None:
            user.password_hash = updated_hash
        user.last_login_at = now
        tokens, _ = self._issue(user, family_id=uuid.uuid4(), now=now)
        await self._session.commit()
        logger.info("Inicio de sesión: usuario %s", user.id)
        return tokens

    async def refresh(self, raw_token: str | None) -> IssuedTokens:
        if not raw_token:
            raise AuthenticationError("invalid_refresh_token")

        now = self._now()
        stored = await self._refresh_tokens.get_by_hash_for_update(hash_refresh_token(raw_token))
        if stored is None or stored.expires_at <= now:
            raise AuthenticationError("invalid_refresh_token")

        if stored.revoked_at is not None:
            await self._reject_revoked_token(stored, stored.revoked_at, now)

        user = await self._users.get_by_id(stored.user_id)
        if user is None or not user.is_active:
            await self._refresh_tokens.revoke_family(stored.family_id, now)
            await self._session.commit()
            raise AuthenticationError("invalid_refresh_token")

        # Rotación: el token usado queda revocado y enlazado a su sustituto.
        stored.revoked_at = now
        tokens, replacement = self._issue(user, family_id=stored.family_id, now=now)
        # El sustituto debe existir antes de referenciarlo (FK inmediata).
        await self._session.flush()
        stored.replaced_by_id = replacement.id
        await self._session.commit()
        return tokens

    async def logout(self, raw_token: str | None, user_id: uuid.UUID) -> None:
        """Revoca la sesión (familia) del refresh token. Idempotente."""
        if not raw_token:
            return
        stored = await self._refresh_tokens.get_by_hash_for_update(hash_refresh_token(raw_token))
        # Solo se revoca una sesión del propio usuario autenticado.
        if stored is not None and stored.user_id == user_id:
            await self._refresh_tokens.revoke_family(stored.family_id, self._now())
            logger.info("Cierre de sesión: usuario %s", user_id)
        await self._session.commit()

    async def get_authenticated_user(self, access_token: str | None) -> User:
        if not access_token:
            raise AuthenticationError("not_authenticated")
        user_id = decode_access_token(
            access_token,
            secret_key=self._settings.jwt_secret_key.get_secret_value(),
            algorithm=self._settings.jwt_algorithm,
        )
        user = await self._users.get_by_id(user_id)
        # Un usuario desactivado pierde el acceso aunque su token no haya caducado.
        if user is None or not user.is_active:
            raise AuthenticationError("invalid_token")
        return user

    # --- internos -------------------------------------------------------

    async def _reject_revoked_token(
        self, stored: RefreshToken, revoked_at: datetime, now: datetime
    ) -> NoReturn:
        rotated_recently = (
            stored.replaced_by_id is not None and now - revoked_at <= REFRESH_REUSE_GRACE
        )
        if not rotated_recently:
            # Reutilización de un token ya rotado o revocado: posible robo.
            # Se invalida toda la sesión.
            await self._refresh_tokens.revoke_family(stored.family_id, now)
            await self._session.commit()
            logger.warning("Reutilización de refresh token: sesión %s revocada", stored.family_id)
            raise AuthenticationError("refresh_token_reused")
        # La cookie del cliente ya contiene el sustituto: puede reintentar.
        raise AuthenticationError("refresh_token_rotated")

    def _issue(
        self, user: User, *, family_id: uuid.UUID, now: datetime
    ) -> tuple[IssuedTokens, RefreshToken]:
        settings = self._settings
        access_lifetime = timedelta(minutes=settings.access_token_expire_minutes)
        access = create_access_token(
            user.id,
            secret_key=settings.jwt_secret_key.get_secret_value(),
            algorithm=settings.jwt_algorithm,
            now=now,
            lifetime=access_lifetime,
        )
        raw_refresh = generate_refresh_token()
        refresh_expires_at = now + timedelta(days=settings.refresh_token_expire_days)
        stored = RefreshToken(
            user_id=user.id,
            family_id=family_id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_expires_at,
        )
        self._refresh_tokens.add(stored)
        tokens = IssuedTokens(
            access_token=access.token,
            access_expires_in=int(access_lifetime.total_seconds()),
            refresh_token=raw_refresh,
            refresh_expires_at=refresh_expires_at,
        )
        return tokens, stored

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)
