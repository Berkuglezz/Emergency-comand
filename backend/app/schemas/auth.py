import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.core.permissions import Permission
from app.domain.enums import RoleCode
from app.schemas.organizations import OrganizationSummary

# Se normaliza a minúsculas: la base de datos exige emails en minúsculas.
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=254),
]
# Límite superior para no hashear con Argon2 entradas arbitrariamente largas.
Password = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class LoginRequest(BaseModel):
    email: Email
    password: Password


class TokenResponse(BaseModel):
    """El refresh token no aparece aquí: viaja solo en una cookie httpOnly."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"  # noqa: S105 — esquema OAuth2, no un secreto
    expires_in: int


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: RoleCode
    permissions: list[Permission]
    organization: OrganizationSummary | None
