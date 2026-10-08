import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import User

# El rol y la organización se necesitan siempre que se carga un usuario
# autenticado; se cargan de forma explícita (las relaciones son lazy="raise").
_WITH_RELATIONS = (selectinload(User.role), selectinload(User.organization))


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        return await self._session.scalar(
            select(User).where(User.email == email).options(*_WITH_RELATIONS)
        )

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._session.scalar(
            select(User).where(User.id == user_id).options(*_WITH_RELATIONS)
        )
