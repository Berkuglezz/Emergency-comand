"""Router raíz de la API v1.

Todo endpoint está protegido por defecto: se registra en `protected` y exige
un access token válido. Solo health, login y refresh se declaran públicos.
"""

from fastapi import APIRouter, Depends, status

from app.api.v1 import auth, dashboard, health, incidents, organizations, resources
from app.api.v1.deps import get_current_user
from app.schemas.errors import ErrorResponse

api_router = APIRouter(prefix="/api/v1")

# --- Públicos (declarados explícitamente) ---------------------------------
api_router.include_router(health.router)
api_router.include_router(auth.public_router)

# --- Protegidos -------------------------------------------------------------
protected = APIRouter(
    dependencies=[Depends(get_current_user)],
    responses={status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse}},
)
protected.include_router(auth.protected_router)
protected.include_router(organizations.router)
protected.include_router(incidents.types_router)
protected.include_router(incidents.router)
protected.include_router(resources.types_router)
protected.include_router(resources.router)
protected.include_router(dashboard.router)

api_router.include_router(protected)
