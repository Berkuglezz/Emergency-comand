"""Inventario de rutas y sus permisos (CLAUDE.md §2.11).

La matriz rol → permisos se prueba en `tests/unit/test_security.py`. Aquí,
cada ruta de la API declara los permisos que exige y el test la llama con los
tres roles: sin alguno de esos permisos, la respuesta debe ser 403
`permission_denied` antes de tocar nada; con ellos, la autorización no debe
bloquearla (la respuesta será 2xx, 404 o 422 según los datos). Una ruta nueva
que no figure en el inventario hace fallar el test.
"""

import re
import uuid

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.domain.enums import RoleCode
from tests.conftest import Headers

P = Permission

PUBLIC: frozenset[Permission] = frozenset()
# Rutas públicas: no exigen sesión (se prueban en test_rbac.py).
PUBLIC_ROUTES = {
    ("GET", "/api/v1/health"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
}

# (método, ruta) → permisos exigidos. Conjunto vacío: basta con la sesión.
ROUTE_PERMISSIONS: dict[tuple[str, str], frozenset[Permission]] = {
    ("POST", "/api/v1/auth/logout"): PUBLIC,
    ("GET", "/api/v1/auth/me"): PUBLIC,
    ("GET", "/api/v1/organizations"): frozenset({P.ORGANIZATIONS_READ}),
    ("GET", "/api/v1/incident-types"): frozenset({P.INCIDENTS_READ}),
    ("GET", "/api/v1/incidents"): frozenset({P.INCIDENTS_READ}),
    ("POST", "/api/v1/incidents"): frozenset({P.INCIDENTS_CREATE}),
    ("GET", "/api/v1/incidents/map"): frozenset({P.INCIDENTS_READ}),
    ("GET", "/api/v1/incidents/{incident_id}"): frozenset({P.INCIDENTS_READ}),
    # Los campos no operativos exigen además `incidents:update` (en el servicio).
    ("PATCH", "/api/v1/incidents/{incident_id}"): frozenset({P.INCIDENTS_UPDATE_OPERATIONAL}),
    ("POST", "/api/v1/incidents/{incident_id}/status"): frozenset({P.INCIDENTS_CHANGE_STATUS}),
    ("GET", "/api/v1/incidents/{incident_id}/events"): frozenset({P.INCIDENTS_READ}),
    ("POST", "/api/v1/incidents/{incident_id}/notes"): frozenset({P.INCIDENTS_ANNOTATE}),
    ("GET", "/api/v1/incidents/{incident_id}/assignments"): frozenset({P.INCIDENTS_READ}),
    ("POST", "/api/v1/incidents/{incident_id}/assignments"): frozenset({P.ASSIGNMENTS_MANAGE}),
    ("GET", "/api/v1/incidents/{incident_id}/assignment-candidates"): frozenset(
        {P.INCIDENTS_READ, P.RESOURCES_READ}
    ),
    ("POST", "/api/v1/assignments/{assignment_id}/arrival"): frozenset({P.ASSIGNMENTS_UPDATE}),
    ("POST", "/api/v1/assignments/{assignment_id}/release"): frozenset({P.ASSIGNMENTS_MANAGE}),
    ("GET", "/api/v1/resource-types"): frozenset({P.RESOURCES_READ}),
    ("GET", "/api/v1/resources"): frozenset({P.RESOURCES_READ}),
    ("POST", "/api/v1/resources"): frozenset({P.RESOURCES_MANAGE}),
    ("GET", "/api/v1/resources/{resource_id}"): frozenset({P.RESOURCES_READ}),
    ("PATCH", "/api/v1/resources/{resource_id}"): frozenset({P.RESOURCES_MANAGE}),
    ("POST", "/api/v1/resources/{resource_id}/status"): frozenset({P.RESOURCES_UPDATE_STATUS}),
    ("GET", "/api/v1/dashboard/summary"): frozenset({P.INCIDENTS_READ, P.RESOURCES_READ}),
}


def _api_routes(app: FastAPI) -> set[tuple[str, str]]:
    return {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }


def test_every_route_declares_its_permissions(app: FastAPI) -> None:
    routes = _api_routes(app)
    assert routes - PUBLIC_ROUTES == set(ROUTE_PERMISSIONS), (
        "Ruta sin declarar en el inventario de permisos (o declarada y ya inexistente)"
    )


def _concrete(path: str) -> str:
    """Sustituye los parámetros de la ruta por identificadores que no existen."""
    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), path)


@pytest.mark.parametrize("role", list(RoleCode))
async def test_each_route_enforces_its_permissions(
    client: AsyncClient, headers: dict[RoleCode, Headers], role: RoleCode
) -> None:
    granted = ROLE_PERMISSIONS[role]
    # El cierre de sesión va el último: no debe afectar al resto de llamadas.
    ordered = sorted(ROUTE_PERMISSIONS.items(), key=lambda item: item[0][1].endswith("/logout"))
    for (method, path), required in ordered:
        body: dict[str, object] | None = {} if method in {"POST", "PATCH"} else None
        response = await client.request(method, _concrete(path), json=body, headers=headers[role])
        if required <= granted:
            assert response.status_code != 403, (role, method, path, response.text)
        else:
            assert response.status_code == 403, (role, method, path, response.status_code)
            assert response.json() == {"detail": "permission_denied"}
