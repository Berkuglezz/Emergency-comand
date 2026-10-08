from collections.abc import Sequence

from app.models import Organization
from app.repositories.organizations import OrganizationRepository


class OrganizationService:
    def __init__(self, organizations: OrganizationRepository) -> None:
        self._organizations = organizations

    async def list_organizations(self) -> Sequence[Organization]:
        return await self._organizations.list_all()
