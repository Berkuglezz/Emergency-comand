"""API de recursos: permisos, ficha, estado, desactivación, filtros y orden.

Todo ocurre dentro de la transacción del test (se deshace al terminar).
"""

import uuid
from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RoleCode
from app.models import Organization, ResourceType
from tests.conftest import API, Headers


async def _org(session: AsyncSession, code: str = "test-org", *, is_active: bool = True) -> str:
    organization = Organization(code=code, name=f"Organización {code}", is_active=is_active)
    session.add(organization)
    await session.commit()
    return str(organization.id)


async def _type_id(session: AsyncSession, code: str) -> str:
    resource_type = (
        await session.scalars(select(ResourceType).where(ResourceType.code == code))
    ).one()
    return str(resource_type.id)


async def _create(
    client: AsyncClient,
    session: AsyncSession,
    headers: Headers,
    *,
    organization_id: str | None = None,
    type_code: str = "fire_engine",
    **fields: Any,
) -> dict[str, Any]:
    body = {
        "code": "BOM-01",
        "name": "Autobomba de prueba",
        "type_id": await _type_id(session, type_code),
        "organization_id": organization_id or await _org(session),
        "municipality": "Oviedo",
        **fields,
    }
    response = await client.post(f"{API}/resources", json=body, headers=headers)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _set_status(
    client: AsyncClient, headers: Headers, resource: dict[str, Any], target: str
) -> dict[str, Any]:
    response = await client.post(
        f"{API}/resources/{resource['id']}/status",
        json={"status": target, "version": resource["version"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


# --- Permisos ------------------------------------------------------------------


async def test_everyone_reads_and_changes_status_but_only_admin_manages(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    resource = await _create(client, session, headers[RoleCode.ADMIN])
    path = f"{API}/resources/{resource['id']}"

    for role in (RoleCode.COORDINATOR, RoleCode.OPERATOR):
        role_headers = headers[role]
        assert (await client.get(f"{API}/resources", headers=role_headers)).status_code == 200
        assert (await client.get(path, headers=role_headers)).status_code == 200
        assert (await client.get(f"{API}/resource-types", headers=role_headers)).status_code == 200

        created = await client.post(
            f"{API}/resources",
            json={
                "code": f"X-{role.value}",
                "name": "x",
                "type_id": resource["type"]["id"],
                "organization_id": resource["organization"]["id"],
                "municipality": "Oviedo",
            },
            headers=role_headers,
        )
        assert created.status_code == 403
        patched = await client.patch(
            path, json={"version": resource["version"], "name": "x"}, headers=role_headers
        )
        assert patched.status_code == 403
        assert patched.json() == {"detail": "permission_denied"}

    # El estado operativo lo puede cambiar cualquier rol (incluido el operador).
    resource = await _set_status(client, headers[RoleCode.OPERATOR], resource, "in_service")
    resource = await _set_status(client, headers[RoleCode.COORDINATOR], resource, "available")
    assert resource["version"] == 3


async def test_requires_authentication(client: AsyncClient) -> None:
    response = await client.get(f"{API}/resources")
    assert response.status_code == 401


# --- Alta ---------------------------------------------------------------------------


async def test_create_resource(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    organization_id = await _org(session)
    resource = await _create(
        client,
        session,
        headers[RoleCode.ADMIN],
        organization_id=organization_id,
        code=" bom-ovi-01 ",
        type_code="ambulance_advanced",
    )

    assert resource["code"] == "BOM-OVI-01"
    assert resource["status"] == "available"
    assert resource["is_active"] is True
    assert resource["is_simulated"] is False
    assert resource["version"] == 1
    assert resource["type"]["code"] == "ambulance_advanced"
    assert resource["type"]["category"] == "medical"
    assert resource["organization"]["id"] == organization_id
    assert resource["municipality"] == "Oviedo"


async def test_create_with_initial_status(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    resource = await _create(client, session, headers[RoleCode.ADMIN], status="out_of_service")
    assert resource["status"] == "out_of_service"


async def test_resource_code_is_unique(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    first = await _create(client, session, admin)
    response = await client.post(
        f"{API}/resources",
        json={
            "code": "bom-01",  # se normaliza a mayúsculas: choca con BOM-01
            "name": "Otra",
            "type_id": first["type"]["id"],
            "organization_id": first["organization"]["id"],
            "municipality": "Gijón",
        },
        headers=admin,
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "resource_code_taken"}


@pytest.mark.parametrize("code", ["", "A", "BOM 01", "-BOM", "BOM_01", "X" * 33])
async def test_invalid_resource_codes_are_rejected(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers], code: str
) -> None:
    response = await client.post(
        f"{API}/resources",
        json={
            "code": code,
            "name": "x",
            "type_id": await _type_id(session, "fire_engine"),
            "organization_id": await _org(session),
            "municipality": "Oviedo",
        },
        headers=headers[RoleCode.ADMIN],
    )
    assert response.status_code == 422


async def test_type_and_organization_must_exist_and_be_active(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    base = {
        "code": "BOM-01",
        "name": "x",
        "type_id": await _type_id(session, "fire_engine"),
        "organization_id": await _org(session),
        "municipality": "Oviedo",
    }
    cases = [
        ({"type_id": str(uuid.uuid4())}, "resource_type_not_found"),
        ({"organization_id": str(uuid.uuid4())}, "organization_not_found"),
        (
            {"organization_id": await _org(session, "inactive-org", is_active=False)},
            "organization_not_found",
        ),
    ]
    for override, code in cases:
        response = await client.post(f"{API}/resources", json={**base, **override}, headers=admin)
        assert response.status_code == 422
        assert response.json() == {"detail": code}


# --- Estado operativo ---------------------------------------------------------------


async def test_status_change_updates_timestamp_and_version(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    resource = await _create(client, session, headers[RoleCode.ADMIN])
    changed = await _set_status(client, headers[RoleCode.OPERATOR], resource, "out_of_service")

    assert changed["status"] == "out_of_service"
    assert changed["version"] == resource["version"] + 1
    assert datetime.fromisoformat(changed["status_changed_at"]) > datetime.fromisoformat(
        resource["status_changed_at"]
    )


async def test_same_status_is_rejected(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    resource = await _create(client, session, headers[RoleCode.ADMIN])
    response = await client.post(
        f"{API}/resources/{resource['id']}/status",
        json={"status": "available", "version": resource["version"]},
        headers=headers[RoleCode.OPERATOR],
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "invalid_transition"}


async def test_stale_version_is_rejected_without_side_effects(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    resource = await _create(client, session, admin)
    path = f"{API}/resources/{resource['id']}"
    await _set_status(client, admin, resource, "in_service")

    stale_status = await client.post(
        f"{path}/status", json={"status": "out_of_service", "version": 1}, headers=admin
    )
    stale_patch = await client.patch(path, json={"version": 1, "name": "Otro"}, headers=admin)

    for response in (stale_status, stale_patch):
        assert response.status_code == 409
        assert response.json() == {"detail": "version_conflict"}
    current = (await client.get(path, headers=admin)).json()
    assert current["status"] == "in_service"
    assert current["name"] == resource["name"]
    assert current["version"] == 2


async def test_inactive_resources_cannot_change_status(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    resource = await _create(client, session, admin)
    path = f"{API}/resources/{resource['id']}"
    resource = (
        await client.patch(
            path, json={"version": resource["version"], "is_active": False}, headers=admin
        )
    ).json()

    response = await client.post(
        f"{path}/status",
        json={"status": "in_service", "version": resource["version"]},
        headers=headers[RoleCode.OPERATOR],
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "resource_inactive"}


# --- Edición de la ficha ---------------------------------------------------------------


async def test_update_resource(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    resource = await _create(client, session, admin)
    other_org = await _org(session, "other-org")

    response = await client.patch(
        f"{API}/resources/{resource['id']}",
        json={
            "version": resource["version"],
            "name": "Autobomba renombrada",
            "type_id": await _type_id(session, "rescue_vehicle"),
            "organization_id": other_org,
            "municipality": "Avilés",
        },
        headers=admin,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["version"] == 2
    assert body["name"] == "Autobomba renombrada"
    assert body["type"]["code"] == "rescue_vehicle"
    assert body["organization"]["id"] == other_org
    assert body["municipality"] == "Avilés"
    # Editar la ficha no toca el estado operativo.
    assert body["status"] == resource["status"]
    assert body["status_changed_at"] == resource["status_changed_at"]


async def test_update_without_changes_writes_nothing(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    resource = await _create(client, session, admin)

    for body in (
        {
            "version": 1,
            "name": resource["name"],
            "type_id": resource["type"]["id"],
            "organization_id": resource["organization"]["id"],
            "municipality": resource["municipality"],
            "is_active": True,
        },
        {"version": 1},
    ):
        response = await client.patch(f"{API}/resources/{resource['id']}", json=body, headers=admin)
        assert response.status_code == 200
        assert response.json()["version"] == 1
        assert response.json()["updated_at"] == resource["updated_at"]


@pytest.mark.parametrize(
    ("body", "status_code", "detail"),
    [
        ({"name": None}, 422, "field_not_nullable"),
        ({"is_active": None}, 422, "field_not_nullable"),
        ({"type_id": str(uuid.uuid4())}, 422, "resource_type_not_found"),
        # El código y el estado no se editan por esta vía.
        ({"code": "OTRO-01"}, 422, None),
        ({"status": "in_service"}, 422, None),
    ],
)
async def test_invalid_updates_are_rejected(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    body: dict[str, Any],
    status_code: int,
    detail: str | None,
) -> None:
    admin = headers[RoleCode.ADMIN]
    resource = await _create(client, session, admin)
    response = await client.patch(
        f"{API}/resources/{resource['id']}", json={"version": 1, **body}, headers=admin
    )
    assert response.status_code == status_code
    if detail:
        assert response.json() == {"detail": detail}


async def test_deactivate_and_reactivate(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    resource = await _create(client, session, admin)
    path = f"{API}/resources/{resource['id']}"

    resource = (
        await client.patch(path, json={"version": 1, "is_active": False}, headers=admin)
    ).json()
    assert resource["is_active"] is False

    active_list = (await client.get(f"{API}/resources", headers=admin)).json()
    full_list = (await client.get(f"{API}/resources?active=false", headers=admin)).json()
    assert active_list["total"] == 0
    assert [item["id"] for item in full_list["items"]] == [resource["id"]]
    # Sigue siendo consultable por id.
    assert (await client.get(path, headers=admin)).status_code == 200

    resource = (
        await client.patch(
            path, json={"version": resource["version"], "is_active": True}, headers=admin
        )
    ).json()
    assert resource["is_active"] is True
    assert resource["version"] == 3


async def test_unknown_resource_returns_404(
    client: AsyncClient, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    path = f"{API}/resources/{uuid.uuid4()}"
    responses = [
        await client.get(path, headers=admin),
        await client.patch(path, json={"version": 1, "name": "x"}, headers=admin),
        await client.post(
            f"{path}/status", json={"status": "in_service", "version": 1}, headers=admin
        ),
    ]
    for response in responses:
        assert response.status_code == 404
        assert response.json() == {"detail": "resource_not_found"}


# --- Listado ---------------------------------------------------------------------------


async def _codes(client: AsyncClient, headers: Headers, **params: Any) -> tuple[list[str], int]:
    response = await client.get(f"{API}/resources", params=params, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    return [item["code"] for item in body["items"]], body["total"]


async def test_filters_sorting_and_pagination(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    org_a = await _org(session, "org-a")
    org_b = await _org(session, "org-b")
    c = await _create(
        client,
        session,
        admin,
        code="C-01",
        name="Unidad sanitaria",
        organization_id=org_a,
        type_code="ambulance_basic",
        municipality="Gijón",
    )
    await _create(
        client,
        session,
        admin,
        code="A-01",
        name="Autobomba norte",
        organization_id=org_a,
        municipality="Oviedo",
    )
    b = await _create(
        client, session, admin, code="B-01", name="Autobomba sur", organization_id=org_b,
        municipality="Avilés",
    )  # fmt: skip
    await _set_status(client, admin, c, "in_service")
    await _set_status(client, admin, b, "out_of_service")

    assert await _codes(client, admin) == (["A-01", "B-01", "C-01"], 3)
    assert await _codes(client, admin, status="in_service") == (["C-01"], 1)
    assert await _codes(client, admin, status=["available", "out_of_service"]) == (
        ["A-01", "B-01"],
        2,
    )
    assert await _codes(client, admin, type="ambulance_basic") == (["C-01"], 1)
    assert await _codes(client, admin, organization_id=org_b) == (["B-01"], 1)
    assert await _codes(client, admin, municipality="gijón") == (["C-01"], 1)
    assert await _codes(client, admin, q="autobomba") == (["A-01", "B-01"], 2)
    assert await _codes(client, admin, q="c-0") == (["C-01"], 1)
    assert await _codes(client, admin, q="%") == ([], 0)

    # Orden por estado: disponible, en servicio, fuera de servicio.
    assert (await _codes(client, admin, sort="status"))[0] == ["A-01", "C-01", "B-01"]
    # Último cambio de estado primero.
    assert (await _codes(client, admin, sort="-status_changed_at"))[0][:2] == ["B-01", "C-01"]

    assert await _codes(client, admin, limit=2, offset=1) == (["B-01", "C-01"], 3)


async def test_resource_types_catalog(
    client: AsyncClient, headers: dict[RoleCode, Headers]
) -> None:
    response = await client.get(f"{API}/resource-types", headers=headers[RoleCode.OPERATOR])
    assert response.status_code == 200
    types = response.json()
    codes = [t["code"] for t in types]
    assert codes == sorted(codes)
    assert "fire_engine" in codes
    assert set(types[0]) == {"id", "code", "category", "icon", "is_active"}
