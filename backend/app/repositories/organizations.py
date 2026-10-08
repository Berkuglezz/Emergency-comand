import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> Sequence[Organization]:
        result = await self._session.scalars(select(Organization).order_by(Organization.name))
        return result.all()

    async def get(self, organization_id: uuid.UUID) -> Organization | None:
        return await self._session.get(Organization, organization_id)
