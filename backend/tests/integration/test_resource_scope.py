"""Ámbito organizativo sobre recursos (CLAUDE.md §2.11, R.4, R.5 y R.6; decisiones
D1, D3, D4, D5, D7 y D9).

Las peticiones van directamente a la API, como haría un cliente que conoce el
identificador de un recurso de otra organización. El operador solo modifica
recursos de su organización (estado operativo y «en el lugar»); sin
organización, ninguno. Coordinador y admin, todos. Un intento rechazado no
cambia nada ni registra eventos.
"""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_access_scope
from app.domain.access_scope import AccessScope, OrganizationAccess
from app.domain.enums import RoleCode
from app.models import IncidentType, Organization, ResourceType
from tests.conftest import API, Headers, MemberHeadersFactory

OUT_OF_SCOPE = {"detail": "organization_out_of_scope"}


async def _organization(session: AsyncSession, code: str) -> str:
    organization = Organization(code=code, name=f"Organización {code}")
    session.add(organization)
    await session.flush()
    return str(organization.id)


async def _resource(
    client: AsyncClient, session: AsyncSession, admin: Headers, code: str, organization_id: str
) -> dict[str, Any]:
    type_id = (
        await session.scalars(select(ResourceType.id).where(ResourceType.code == "fire_engine"))
    ).one()
    response = await client.post(
        f"{API}/resources",
        json={
            "code": code,
            "name": f"Recurso {code}",
            "type_id": str(type_id),
            "organization_id": organization_id,
            "base": {"municipality": "Gijón", "latitude": 43.5357, "longitude": -5.6615},
        },
        headers=admin,
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _incident(client: AsyncClient, session: AsyncSession, admin: Headers) -> dict[str, Any]:
    type_id = (
        await session.scalars(select(IncidentType.id).where(IncidentType.code == "structure_fire"))
    ).one()
    response = await client.post(
        f"{API}/incidents",
        json={
            "type_id": str(type_id),
            "title": "Incidente con recursos de dos organizaciones",
            "location": {"municipality": "Oviedo", "latitude": 43.3614, "longitude": -5.8494},
        },
        headers=admin,
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _get(client: AsyncClient, headers: Headers, path: str) -> Any:
    response = await client.get(f"{API}/{path}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class World:
    """Dos organizaciones (A y B), un recurso libre y otro asignado en cada una."""

    def __init__(self) -> None:
        self.org_a = ""
        self.org_b = ""
        self.free_a: dict[str, Any] = {}
        self.free_b: dict[str, Any] = {}
        self.incident: dict[str, Any] = {}
        self.assignment_a: dict[str, Any] = {}
        self.assignment_b: dict[str, Any] = {}


@pytest.fixture
async def world(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> World:
    admin = headers[RoleCode.ADMIN]
    w = World()
    w.org_a = await _organization(session, "scope-a")
    w.org_b = await _organization(session, "scope-b")
    w.free_a = await _resource(client, session, admin, "SCP-A-LIBRE", w.org_a)
    w.free_b = await _resource(client, session, admin, "SCP-B-LIBRE", w.org_b)
    assigned_a = await _resource(client, session, admin, "SCP-A-ASIG", w.org_a)
    assigned_b = await _resource(client, session, admin, "SCP-B-ASIG", w.org_b)

    incident = await _incident(client, session, admin)
    for resource in (assigned_a, assigned_b):
        response = await client.post(
            f"{API}/incidents/{incident['id']}/assignments",
            json={"resource_id": resource["id"], "version": incident["version"]},
            headers=admin,
        )
        assert response.status_code == 200, response.text
        incident = response.json()
    w.incident = incident
    assignments = await _get(client, admin, f"incidents/{incident['id']}/assignments")
    by_code = {assignment["resource"]["code"]: assignment for assignment in assignments}
    w.assignment_a = by_code["SCP-A-ASIG"]
    w.assignment_b = by_code["SCP-B-ASIG"]
    return w


async def _change_status(
    client: AsyncClient, headers: Headers, resource: dict[str, Any], target: str = "in_service"
) -> Any:
    return await client.post(
        f"{API}/resources/{resource['id']}/status",
        json={"status": target, "version": resource["version"]},
        headers=headers,
    )


async def _arrive(
    client: AsyncClient, headers: Headers, world: World, assignment: dict[str, Any]
) -> Any:
    return await client.post(
        f"{API}/assignments/{assignment['id']}/arrival",
        json={"version": world.incident["version"]},
        headers=headers,
    )


async def _incident_state(client: AsyncClient, admin: Headers, world: World) -> tuple[Any, ...]:
    incident_id = world.incident["id"]
    return (
        await _get(client, admin, f"incidents/{incident_id}"),
        await _get(client, admin, f"incidents/{incident_id}/events"),
        await _get(client, admin, f"incidents/{incident_id}/assignments"),
    )


# --- Estado operativo del recurso -----------------------------------------------------


async def test_operator_changes_status_of_its_own_organization(
    client: AsyncClient, member_headers: MemberHeadersFactory, world: World
) -> None:
    operator = await member_headers(RoleCode.OPERATOR, world.org_a)

    response = await _change_status(client, operator, world.free_a)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "in_service"


async def test_operator_cannot_change_status_of_another_organization(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    member_headers: MemberHeadersFactory,
    world: World,
) -> None:
    operator = await member_headers(RoleCode.OPERATOR, world.org_a)
    path = f"resources/{world.free_b['id']}"
    # D4: lo ve (lectura de todas las organizaciones)…
    before = await _get(client, operator, path)

    # …pero no lo modifica, aunque conozca su identificador y su versión.
    response = await _change_status(client, operator, world.free_b, "out_of_service")

    assert response.status_code == 403
    assert response.json() == OUT_OF_SCOPE
    assert await _get(client, headers[RoleCode.ADMIN], path) == before


async def test_scope_is_checked_before_the_version(
    client: AsyncClient, member_headers: MemberHeadersFactory, world: World
) -> None:
    """Con una versión obsoleta, la respuesta sigue siendo 403 y no 409."""
    operator = await member_headers(RoleCode.OPERATOR, world.org_a)
    stale = {**world.free_b, "version": world.free_b["version"] + 7}

    response = await _change_status(client, operator, stale)

    assert response.status_code == 403
    assert response.json() == OUT_OF_SCOPE


async def test_operator_without_organization_cannot_change_any_status(
    client: AsyncClient, headers: dict[RoleCode, Headers], world: World
) -> None:
    operator = headers[RoleCode.OPERATOR]  # usuario sin organización (D3)
    admin = headers[RoleCode.ADMIN]

    for resource in (world.free_a, world.free_b):
        before = await _get(client, admin, f"resources/{resource['id']}")
        response = await _change_status(client, operator, resource)
        assert response.status_code == 403
        assert response.json() == OUT_OF_SCOPE
        assert await _get(client, admin, f"resources/{resource['id']}") == before


async def test_coordinator_and_admin_change_any_organization(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    member_headers: MemberHeadersFactory,
    world: World,
) -> None:
    # El coordinador pertenece a A y modifica un recurso de B (D1).
    coordinator = await member_headers(RoleCode.COORDINATOR, world.org_a)
    changed = await _change_status(client, coordinator, world.free_b)
    assert changed.status_code == 200, changed.text

    # El admin de prueba no tiene organización y modifica igualmente.
    response = await _change_status(client, headers[RoleCode.ADMIN], world.free_a)
    assert response.status_code == 200, response.text


# --- «En el lugar» ------------------------------------------------------------------


async def test_operator_marks_arrival_of_its_own_resource(
    client: AsyncClient, member_headers: MemberHeadersFactory, world: World
) -> None:
    operator = await member_headers(RoleCode.OPERATOR, world.org_a)

    response = await _arrive(client, operator, world, world.assignment_a)

    assert response.status_code == 200, response.text
    assignments = await _get(client, operator, f"incidents/{world.incident['id']}/assignments")
    arrived = {a["resource"]["code"]: a["arrived_at"] for a in assignments}
    assert arrived["SCP-A-ASIG"] is not None
    assert arrived["SCP-B-ASIG"] is None


async def test_operator_cannot_mark_arrival_of_another_organization(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    member_headers: MemberHeadersFactory,
    world: World,
) -> None:
    operator = await member_headers(RoleCode.OPERATOR, world.org_a)
    admin = headers[RoleCode.ADMIN]
    before = await _incident_state(client, admin, world)

    response = await _arrive(client, operator, world, world.assignment_b)

    assert response.status_code == 403
    assert response.json() == OUT_OF_SCOPE
    # Ni `arrived_at`, ni `version` del incidente, ni eventos.
    assert await _incident_state(client, admin, world) == before


async def test_operator_without_organization_cannot_mark_any_arrival(
    client: AsyncClient, headers: dict[RoleCode, Headers], world: World
) -> None:
    admin = headers[RoleCode.ADMIN]
    before = await _incident_state(client, admin, world)

    for assignment in (world.assignment_a, world.assignment_b):
        response = await _arrive(client, headers[RoleCode.OPERATOR], world, assignment)
        assert response.status_code == 403
        assert response.json() == OUT_OF_SCOPE

    assert await _incident_state(client, admin, world) == before


async def test_coordinator_marks_arrival_of_any_organization(
    client: AsyncClient, member_headers: MemberHeadersFactory, world: World
) -> None:
    coordinator = await member_headers(RoleCode.COORDINATOR, world.org_a)

    response = await _arrive(client, coordinator, world, world.assignment_b)

    assert response.status_code == 200, response.text


# --- Asignar, retirar y reasignar (R.5) -------------------------------------------------


@pytest.fixture
def restrict_scope(app: FastAPI) -> Iterator[Any]:
    """Limita el ámbito de escritura de las peticiones siguientes a unas
    organizaciones. Hoy ningún rol lo tiene así (D1: el coordinador alcanza a
    todas); prepara el caso de una autorización por organización."""

    def _restrict(*organization_ids: str) -> None:
        scope = AccessScope(
            read=OrganizationAccess.everything(),
            write=OrganizationAccess.only(*(uuid.UUID(org) for org in organization_ids)),
        )
        app.dependency_overrides[get_access_scope] = lambda: scope

    yield _restrict
    app.dependency_overrides.pop(get_access_scope, None)


async def _assign(
    client: AsyncClient, headers: Headers, incident: dict[str, Any], resource_id: str, **extra: Any
) -> Any:
    return await client.post(
        f"{API}/incidents/{incident['id']}/assignments",
        json={"resource_id": resource_id, "version": incident["version"], **extra},
        headers=headers,
    )


async def _candidate_codes(
    client: AsyncClient, headers: Headers, incident_id: str, **query: Any
) -> set[str]:
    response = await client.get(
        f"{API}/incidents/{incident_id}/assignment-candidates",
        params={"include_assigned": "true", **query},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return {candidate["resource"]["code"] for candidate in response.json()}


async def test_coordinator_assigns_resources_of_several_organizations(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    member_headers: MemberHeadersFactory,
    world: World,
) -> None:
    coordinator = await member_headers(RoleCode.COORDINATOR, world.org_a)
    incident = await _incident(client, session, headers[RoleCode.ADMIN])

    first = await _assign(client, coordinator, incident, world.free_a["id"])
    assert first.status_code == 200, first.text
    second = await _assign(client, coordinator, first.json(), world.free_b["id"])
    assert second.status_code == 200, second.text
    assert second.json()["active_assignments"] == 2


async def test_restricted_scope_cannot_assign_out_of_scope(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    world: World,
    restrict_scope: Any,
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _incident(client, session, admin)
    resource_before = await _get(client, admin, f"resources/{world.free_b['id']}")
    incident_before = (
        await _get(client, admin, f"incidents/{incident['id']}"),
        await _get(client, admin, f"incidents/{incident['id']}/events"),
    )
    restrict_scope(world.org_a)

    response = await _assign(client, headers[RoleCode.COORDINATOR], incident, world.free_b["id"])

    assert response.status_code == 403
    assert response.json() == OUT_OF_SCOPE
    # Sin asignación, sin cambio de estado del recurso ni del incidente, sin eventos.
    assert await _get(client, admin, f"resources/{world.free_b['id']}") == resource_before
    assert (
        await _get(client, admin, f"incidents/{incident['id']}"),
        await _get(client, admin, f"incidents/{incident['id']}/events"),
    ) == incident_before
    # Dentro del ámbito, sí.
    allowed = await _assign(client, headers[RoleCode.COORDINATOR], incident, world.free_a["id"])
    assert allowed.status_code == 200, allowed.text


async def test_restricted_scope_cannot_release_out_of_scope(
    client: AsyncClient, headers: dict[RoleCode, Headers], world: World, restrict_scope: Any
) -> None:
    admin = headers[RoleCode.ADMIN]
    before = await _incident_state(client, admin, world)
    restrict_scope(world.org_a)

    response = await client.post(
        f"{API}/assignments/{world.assignment_b['id']}/release",
        json={"reason": "completed", "version": world.incident["version"]},
        headers=headers[RoleCode.COORDINATOR],
    )

    assert response.status_code == 403
    assert response.json() == OUT_OF_SCOPE
    assert await _incident_state(client, admin, world) == before


async def test_restricted_scope_cannot_reassign_out_of_scope(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    world: World,
    restrict_scope: Any,
) -> None:
    admin = headers[RoleCode.ADMIN]
    target = await _incident(client, session, admin)
    origin_before = await _incident_state(client, admin, world)
    target_before = await _get(client, admin, f"incidents/{target['id']}/events")
    restrict_scope(world.org_a)

    response = await _assign(
        client,
        headers[RoleCode.COORDINATOR],
        target,
        world.assignment_b["resource"]["id"],
        reassign=True,
    )

    assert response.status_code == 403
    assert response.json() == OUT_OF_SCOPE
    # Ni se retira del origen ni se asigna al destino.
    assert await _incident_state(client, admin, world) == origin_before
    assert await _get(client, admin, f"incidents/{target['id']}/events") == target_before


async def test_candidates_are_limited_to_the_write_scope(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    member_headers: MemberHeadersFactory,
    world: World,
    restrict_scope: Any,
) -> None:
    incident_id = world.incident["id"]
    coordinator = headers[RoleCode.COORDINATOR]
    every = await _candidate_codes(client, coordinator, incident_id)
    assert {"SCP-A-LIBRE", "SCP-B-LIBRE"} <= every

    # El operador solo ve como candidatos los de su organización (no asigna,
    # pero la lista es «a quién podría asignar»); sin organización, ninguno.
    operator = await member_headers(RoleCode.OPERATOR, world.org_a)
    assert "SCP-B-LIBRE" not in await _candidate_codes(client, operator, incident_id)
    assert "SCP-A-LIBRE" in await _candidate_codes(client, operator, incident_id)
    assert await _candidate_codes(client, headers[RoleCode.OPERATOR], incident_id) == set()

    restrict_scope(world.org_a)
    limited = await _candidate_codes(client, coordinator, incident_id)
    assert "SCP-A-LIBRE" in limited
    assert not any(code.startswith("SCP-B") for code in limited)
    # Pedir expresamente otra organización no salta el ámbito.
    assert (
        await _candidate_codes(client, coordinator, incident_id, organization_id=world.org_b)
        == set()
    )


# --- Lectura (R.6) ----------------------------------------------------------------------


async def _resource_codes(client: AsyncClient, headers: Headers, **query: Any) -> set[str]:
    response = await client.get(f"{API}/resources", params={"limit": 100, **query}, headers=headers)
    assert response.status_code == 200, response.text
    return {item["code"] for item in response.json()["items"]}


@pytest.mark.parametrize("with_organization", [True, False])
async def test_operator_keeps_reading_every_organization(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    member_headers: MemberHeadersFactory,
    world: World,
    with_organization: bool,
) -> None:
    """D4: el ámbito de escritura (solo A, o ninguna) no limita la lectura."""
    operator = (
        await member_headers(RoleCode.OPERATOR, world.org_a)
        if with_organization
        else headers[RoleCode.OPERATOR]
    )
    incident_id = world.incident["id"]

    assert {"SCP-A-LIBRE", "SCP-B-LIBRE", "SCP-B-ASIG"} <= await _resource_codes(client, operator)
    assert await _resource_codes(client, operator, organization_id=world.org_b) == {
        "SCP-B-LIBRE",
        "SCP-B-ASIG",
    }
    resource_b = await _get(client, operator, f"resources/{world.free_b['id']}")
    assert resource_b["organization"]["id"] == world.org_b
    # Incidentes, asignaciones (con recursos de B), historial y resumen.
    await _get(client, operator, f"incidents/{incident_id}")
    assignments = await _get(client, operator, f"incidents/{incident_id}/assignments")
    assert {a["resource"]["code"] for a in assignments} == {"SCP-A-ASIG", "SCP-B-ASIG"}
    await _get(client, operator, f"incidents/{incident_id}/events")
    summary = await _get(client, operator, "dashboard/summary")
    assert summary["resources"]["active_total"] >= 4


async def test_missing_resource_is_still_not_found(
    client: AsyncClient, headers: dict[RoleCode, Headers]
) -> None:
    response = await client.get(
        f"{API}/resources/{uuid.uuid4()}", headers=headers[RoleCode.OPERATOR]
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "resource_not_found"}


@pytest.fixture
def restrict_read(app: FastAPI) -> Iterator[Any]:
    """Limita el ámbito de **lectura**. Ningún rol lo tiene hoy (D4): prueba que el
    patrón está listo para cuando exista."""

    def _restrict(*organization_ids: str) -> None:
        scope = AccessScope(
            read=OrganizationAccess.only(*(uuid.UUID(org) for org in organization_ids)),
            write=OrganizationAccess.nothing(),
        )
        app.dependency_overrides[get_access_scope] = lambda: scope

    yield _restrict
    app.dependency_overrides.pop(get_access_scope, None)


async def test_restricted_read_scope_hides_other_organizations(
    client: AsyncClient, headers: dict[RoleCode, Headers], world: World, restrict_read: Any
) -> None:
    operator = headers[RoleCode.OPERATOR]
    restrict_read(world.org_a)

    # Fuera del ámbito de lectura, la ficha responde como si no existiera (D5).
    hidden = await client.get(f"{API}/resources/{world.free_b['id']}", headers=operator)
    assert hidden.status_code == 404
    assert hidden.json() == {"detail": "resource_not_found"}
    assert (
        await client.get(f"{API}/resources/{world.free_a['id']}", headers=operator)
    ).status_code == 200

    # El listado (y su total) solo incluye el ámbito, aunque se pida otra organización.
    codes = await _resource_codes(client, operator)
    assert {"SCP-A-LIBRE", "SCP-A-ASIG"} <= codes
    assert not any(code.startswith("SCP-B") for code in codes)
    response = await client.get(
        f"{API}/resources", params={"organization_id": world.org_b}, headers=operator
    )
    assert response.json()["total"] == 0
