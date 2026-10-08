"""El seed de demostración es idempotente y solo crea datos marcados como simulados."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import verify_password
from app.domain.enums import RoleCode
from app.models import Organization, User
from seeds import seed as seed_module
from seeds.fixtures import INCIDENTS, ORGANIZATIONS, RESOURCES, USERS
from seeds.seed import seed

DEMO_PASSWORD = "demo-password-for-tests"


async def _counts(session: AsyncSession) -> tuple[int, int]:
    users = await session.scalar(select(func.count()).select_from(User))
    organizations = await session.scalar(select(func.count()).select_from(Organization))
    return users or 0, organizations or 0


async def test_seed_creates_one_demo_user_per_role(session: AsyncSession) -> None:
    report = await seed(session, DEMO_PASSWORD)

    assert len(report.created) == len(USERS) + len(ORGANIZATIONS) + len(RESOURCES) + len(INCIDENTS)
    users = (await session.scalars(select(User).options(selectinload(User.role)))).all()
    assert sorted(user.role.code for user in users) == sorted(RoleCode)
    for user in users:
        assert user.is_active
        assert user.email.endswith(".test")
        assert verify_password(DEMO_PASSWORD, user.password_hash)[0]
        assert DEMO_PASSWORD not in user.password_hash


async def test_seed_organizations_are_marked_as_simulated(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    organizations = (await session.scalars(select(Organization))).all()
    assert {org.code for org in organizations} == {o.code for o in ORGANIZATIONS}
    for org in organizations:
        assert org.is_simulated
        assert org.code.startswith("sim-")
        assert "(simulado)" in org.name


async def test_seed_is_idempotent(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)
    counts = await _counts(session)
    hashes = dict((await session.execute(select(User.email, User.password_hash))).all())

    second = await seed(session, DEMO_PASSWORD)
    third = await seed(session, DEMO_PASSWORD)

    assert not second.changed
    assert not third.changed
    assert await _counts(session) == counts
    # Sin cambios en los hashes: el seed no re-hashea en cada ejecución.
    session.expire_all()
    after = dict((await session.execute(select(User.email, User.password_hash))).all())
    assert after == hashes


async def test_seed_restores_modified_demo_data(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)
    operator = (await session.scalars(select(User).where(User.email == USERS[2].email))).one()
    operator.is_active = False
    operator.full_name = "Modificado"
    await session.commit()

    report = await seed(session, DEMO_PASSWORD)

    assert report.updated == [f"user:{USERS[2].email}"]
    await session.refresh(operator)
    assert operator.is_active
    assert operator.full_name == USERS[2].full_name


async def test_seed_updates_password_when_it_changes(session: AsyncSession) -> None:
    await seed(session, DEMO_PASSWORD)

    report = await seed(session, "a-new-demo-password")

    assert len(report.updated) == len(USERS)
    for user in await session.scalars(select(User)):
        assert verify_password("a-new-demo-password", user.password_hash)[0]


async def test_seed_entrypoint_refuses_outside_development(session: AsyncSession) -> None:
    # Los tests corren con ENVIRONMENT=test: el seed termina con error sin tocar nada.
    assert await seed_module._main() == 1
    assert await _counts(session) == (0, 0)
