import uuid

from pydantic import BaseModel, ConfigDict


class OrganizationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    is_simulated: bool


class OrganizationResponse(OrganizationSummary):
    is_active: bool
