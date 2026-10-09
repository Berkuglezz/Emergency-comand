"""Dependencias compartidas de los routers v1."""

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.permissions import Permission, has_permission
from app.db.session import get_session
from app.domain.exceptions import PermissionDeniedError
from app.models import User
from app.repositories.health import DatabaseHealthRepository
from app.repositories.organizations import OrganizationRepository
from app.services.assignments import AssignmentService
from app.services.auth import AuthService
from app.services.dashboard import DashboardService
from app.services.health import HealthService
from app.services.incidents import IncidentService
from app.services.organizations import OrganizationService
from app.services.resources import ResourceService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

# auto_error=False: la ausencia de token se traduce a nuestro propio 401
# con código, igual que el resto de errores de autenticación.
_bearer = HTTPBearer(auto_error=False)


# --- Servicios -------------------------------------------------------------


def get_health_service(session: SessionDep) -> HealthService:
    return HealthService(DatabaseHealthRepository(session))


def get_auth_service(session: SessionDep, settings: SettingsDep) -> AuthService:
    return AuthService(session, settings)


def get_organization_service(session: SessionDep) -> OrganizationService:
    return OrganizationService(OrganizationRepository(session))


def get_incident_service(session: SessionDep) -> IncidentService:
    return IncidentService(session)


def get_resource_service(session: SessionDep) -> ResourceService:
    return ResourceService(session)


def get_dashboard_service(session: SessionDep) -> DashboardService:
    return DashboardService(session)


def get_assignment_service(session: SessionDep) -> AssignmentService:
    return AssignmentService(session)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
OrganizationServiceDep = Annotated[OrganizationService, Depends(get_organization_service)]
IncidentServiceDep = Annotated[IncidentService, Depends(get_incident_service)]
ResourceServiceDep = Annotated[ResourceService, Depends(get_resource_service)]
DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]
AssignmentServiceDep = Annotated[AssignmentService, Depends(get_assignment_service)]


# --- Autenticación y autorización -----------------------------------------


async def get_current_user(
    auth: AuthServiceDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    return await auth.get_authenticated_user(credentials.credentials if credentials else None)


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_permission(permission: Permission) -> Callable[[User], Awaitable[User]]:
    """Dependencia que exige un permiso al usuario autenticado (403 si no lo tiene)."""

    async def dependency(user: CurrentUserDep) -> User:
        if not has_permission(user.role.code, permission):
            raise PermissionDeniedError()
        return user

    return dependency
