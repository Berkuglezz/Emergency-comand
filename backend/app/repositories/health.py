from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class DatabaseHealthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ping(self) -> None:
        """Lanza una excepción si la base de datos no responde."""
        await self._session.execute(text("SELECT 1"))
