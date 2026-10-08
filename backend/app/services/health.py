import logging
from typing import Protocol

from sqlalchemy.exc import SQLAlchemyError

from app.domain.enums import ComponentStatus, HealthStatus
from app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)


class DatabasePinger(Protocol):
    async def ping(self) -> None: ...


class HealthService:
    def __init__(self, database: DatabasePinger) -> None:
        self._database = database

    async def check(self) -> HealthResponse:
        database = await self._check_database()
        status = HealthStatus.OK if database is ComponentStatus.OK else HealthStatus.DEGRADED
        return HealthResponse(status=status, database=database)

    async def _check_database(self) -> ComponentStatus:
        try:
            await self._database.ping()
        except (SQLAlchemyError, OSError) as exc:
            # Solo el tipo: el mensaje del driver podría incluir datos de conexión.
            logger.warning("Base de datos no disponible: %s", type(exc).__name__)
            return ComponentStatus.UNAVAILABLE
        return ComponentStatus.OK
