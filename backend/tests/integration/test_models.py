"""Los modelos funcionan contra el esquema real que crea la migración."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import RoleCode
from app.models import Organization, RefreshToken, Role, User


async def _role(session: AsyncSession, code: RoleCode) -> Role:
    return (await session.scalars(select(Role).where(Role.code == code))).one()


async def test_migration_creates_the_three_roles(session: AsyncSession) -> None:
    codes = set(await session.scalars(select(Role.code)))
    assert codes == set(RoleCode)


async def test_user_with_role_and_organization(session: AsyncSession) -> None:
    organization = Organization(code="test-org", name="Organización de prueba")
    user = User(
        email="tester@example.test",
        full_name="Usuario de prueba",
        password_hash="not-a-real-hash",
        role=await _role(session, RoleCode.COORDINATOR),
        organization=organization,
    )
    session.add(user)
    await session.flush()

    loaded = (
        await session.scalars(
            select(User)
            .where(User.id == user.id)
            .options(selectinload(User.role), selectinload(User.organization))
            .execution_options(populate_existing=True)
        )
    ).one()

    assert loaded.role.code is RoleCode.COORDINATOR
    assert loaded.organization is not None
    assert loaded.organization.is_simulated is False
    assert loaded.is_active is True
    assert loaded.created_at.tzinfo is not None


async def test_relationships_are_never_lazy_loaded(session: AsyncSession) -> None:
    session.add(
        User(
            email="lazy@example.test",
            full_name="Lazy",
            password_hash="not-a-real-hash",
            role_id=(await _role(session, RoleCode.OPERATOR)).id,
        )
    )
    await session.flush()
    session.expunge_all()

    user = (await session.scalars(select(User).where(User.email == "lazy@example.test"))).one()

    with pytest.raises(InvalidRequestError):
        _ = user.role


async def test_email_must_be_lowercase(session: AsyncSession) -> None:
    session.add(
        User(
            email="Upper@Example.test",
            full_name="Upper",
            password_hash="not-a-real-hash",
            role_id=(await _role(session, RoleCode.OPERATOR)).id,
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()


async def test_refresh_tokens_are_deleted_with_their_user(session: AsyncSession) -> None:
    user = User(
        email="tokens@example.test",
        full_name="Tokens",
        password_hash="not-a-real-hash",
        role_id=(await _role(session, RoleCode.OPERATOR)).id,
    )
    session.add(user)
    await session.flush()
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=uuid.uuid4(),
            token_hash="a" * 64,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )
    )
    await session.flush()

    await session.delete(user)
    await session.flush()

    remaining = await session.scalars(select(RefreshToken).where(RefreshToken.user_id == user.id))
    assert remaining.all() == []
