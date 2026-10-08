"""Utilidades de transacción compartidas por los servicios."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.domain.exceptions import ConflictError


async def commit_or_conflict(session: AsyncSession) -> None:
    """Confirma la transacción. Si el bloqueo optimista (`version`) detecta que
    la fila cambió entretanto, deshace todo y lanza `version_conflict`."""
    try:
        await session.commit()
    except StaleDataError as exc:
        await session.rollback()
        raise ConflictError("version_conflict") from exc
