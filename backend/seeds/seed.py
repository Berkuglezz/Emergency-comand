"""Seed de demostración idempotente.

    python -m seeds.seed

- Solo se ejecuta con ENVIRONMENT=development.
- Se puede ejecutar cualquier número de veces sin duplicar nada:
  - usuarios y organizaciones: crea lo que falta y devuelve lo existente al
    estado de `fixtures.py`;
  - recursos e incidentes simulados: solo crea lo que falta y no deshace los
    cambios hechos durante la demo (ver `seeds/operational.py`).
- La contraseña de los usuarios demo sale de DEMO_USER_PASSWORD (.env); no
  está escrita en el código.
"""

import asyncio
import logging
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ENV_FILES, get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password, verify_password
from app.db.session import dispose_engine, get_sessionmaker
from app.models import Organization, Role, User
from seeds.fixtures import ORGANIZATIONS, USERS
from seeds.operational import seed_incidents, seed_resources

logger = logging.getLogger("seeds")

# Clave arbitraria del cerrojo consultivo: dos seeds simultáneos se serializan.
_SEED_LOCK_KEY = 7_311_200_001


class SeedSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    demo_user_password: SecretStr = Field(min_length=12)


@dataclass
class SeedReport:
    created: list[str] = field(default_factory=list)
    updated: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated)


async def seed(session: AsyncSession, demo_password: str) -> SeedReport:
    """Aplica los datos de demo en una única transacción."""
    report = SeedReport()
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _SEED_LOCK_KEY})

    organizations = await _seed_organizations(session, report)
    await _seed_users(session, organizations, demo_password, report)
    now = datetime.now(UTC)
    report.created += await seed_resources(session, organizations, now)
    report.created += await seed_incidents(session, now)

    await session.commit()
    return report


async def _seed_organizations(session: AsyncSession, report: SeedReport) -> dict[str, Organization]:
    existing = {
        org.code: org
        for org in await session.scalars(
            select(Organization).where(Organization.code.in_([o.code for o in ORGANIZATIONS]))
        )
    }
    for fixture in ORGANIZATIONS:
        org = existing.get(fixture.code)
        if org is None:
            org = Organization(code=fixture.code, name=fixture.name, is_simulated=True)
            session.add(org)
            existing[fixture.code] = org
            report.created.append(f"organization:{fixture.code}")
        elif (org.name, org.is_simulated, org.is_active) != (fixture.name, True, True):
            org.name, org.is_simulated, org.is_active = fixture.name, True, True
            report.updated.append(f"organization:{fixture.code}")
    await session.flush()
    return existing


async def _seed_users(
    session: AsyncSession,
    organizations: dict[str, Organization],
    demo_password: str,
    report: SeedReport,
) -> None:
    roles = {role.code: role for role in await session.scalars(select(Role))}
    existing = {
        user.email: user
        for user in await session.scalars(
            select(User).where(User.email.in_([u.email for u in USERS]))
        )
    }
    for fixture in USERS:
        role = roles[fixture.role]
        organization_id = (
            organizations[fixture.organization_code].id if fixture.organization_code else None
        )
        user = existing.get(fixture.email)
        if user is None:
            session.add(
                User(
                    email=fixture.email,
                    full_name=fixture.full_name,
                    password_hash=hash_password(demo_password),
                    role_id=role.id,
                    organization_id=organization_id,
                )
            )
            report.created.append(f"user:{fixture.email}")
            continue

        changed = False
        expected = (fixture.full_name, role.id, organization_id, True)
        if (user.full_name, user.role_id, user.organization_id, user.is_active) != expected:
            user.full_name, user.role_id, user.organization_id, user.is_active = expected
            changed = True
        # Solo se vuelve a hashear si la contraseña ha cambiado en .env: un
        # hash nuevo en cada ejecución no sería idempotente.
        if not verify_password(demo_password, user.password_hash)[0]:
            user.password_hash = hash_password(demo_password)
            changed = True
        if changed:
            report.updated.append(f"user:{fixture.email}")


async def _main() -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    if not settings.is_development:
        logger.error("El seed de demostración solo se ejecuta con ENVIRONMENT=development")
        return 1

    demo_password = SeedSettings().demo_user_password.get_secret_value()
    try:
        async with get_sessionmaker()() as session:
            report = await seed(session, demo_password)
    finally:
        await dispose_engine()

    if report.changed:
        logger.info("Seed aplicado. Creado: %s. Actualizado: %s.", report.created, report.updated)
    else:
        logger.info("Seed sin cambios: los datos de demostración ya estaban al día.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
