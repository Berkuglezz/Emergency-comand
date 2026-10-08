from pydantic import BaseModel

from app.domain.enums import ComponentStatus, HealthStatus


class HealthResponse(BaseModel):
    status: HealthStatus
    database: ComponentStatus
