"""Asignación de recursos a incidentes (Fase 4, CLAUDE.md §2.8): efectos,
reglas, historial, permisos, candidatos y ETA estimada."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RoleCode
from app.models import IncidentType, Organization, ResourceType
from tests.conftest import API, Headers, MemberHeadersFactory

OVIEDO = {"latitude": 43.3614, "longitude": -5.8494}
GIJON = {"latitude": 43.5357, "longitude": -5.6615}
AVILES = {"latitude": 43.5547, "longitude": -5.9248}


async def _org(session: AsyncSession) -> str:
    organization = Organization(code="asg-org", name="Organización de prueba")
    session.add(organization)
    await session.flush()
    return str(organization.id)


async def _incident(
    client: AsyncClient,
    session: AsyncSession,
    headers: Headers,
    *,
    type_code: str = "structure_fire",
    coordinates: dict[str, float] | None = OVIEDO,
    **fields: Any,
) -> dict[str, Any]:
    type_id = (
        await session.scalars(select(IncidentType.id).where(IncidentType.code == type_code))
    ).one()
    body = {
        "type_id": str(type_id),
        "title": "Incidente de prueba",
        "location": {"municipality": "Oviedo", **(coordinates or {})},
        **fields,
    }
    response = await client.post(f"{API}/incidents", json=body, headers=headers)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _resource(
    client: AsyncClient,
    session: AsyncSession,
    headers: Headers,
    code: str,
    *,
    organization_id: str,
    type_code: str = "fire_engine",
    base: dict[str, float] | None = GIJON,
) -> dict[str, Any]:
    type_id = (
        await session.scalars(select(ResourceType.id).where(ResourceType.code == type_code))
    ).one()
    response = await client.post(
        f"{API}/resources",
        json={
            "code": code,
            "name": f"Recurso {code}",
            "type_id": str(type_id),
            "organization_id": organization_id,
            "base": {"municipality": "Gijón", **(base or {})},
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _assign(
    client: AsyncClient,
    headers: Headers,
    incident: dict[str, Any],
    resource: dict[str, Any],
    **extra: Any,
) -> Any:
    return await client.post(
        f"{API}/incidents/{incident['id']}/assignments",
        json={"resource_id": resource["id"], "version": incident["version"], **extra},
        headers=headers,
    )


async def _assignments(
    client: AsyncClient, headers: Headers, incident: dict[str, Any]
) -> list[dict[str, Any]]:
    response = await client.get(f"{API}/incidents/{incident['id']}/assignments", headers=headers)
    assert response.status_code == 200, response.text
    data: list[dict[str, Any]] = response.json()
    return data


async def _events(
    client: AsyncClient, headers: Headers, incident: dict[str, Any]
) -> list[dict[str, Any]]:
    response = await client.get(f"{API}/incidents/{incident['id']}/events", headers=headers)
    data: list[dict[str, Any]] = response.json()
    return data


async def _get(client: AsyncClient, headers: Headers, path: str) -> dict[str, Any]:
    response = await client.get(f"{API}/{path}", headers=headers)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


@pytest.fixture
async def setup(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Un incidente con coordenadas y un recurso disponible con base."""
    admin = headers[RoleCode.ADMIN]
    organization = await _org(session)
    incident = await _incident(client, session, admin)
    resource = await _resource(client, session, admin, "ASG-01", organization_id=organization)
    return incident, resource, organization


# --- Asignar ------------------------------------------------------------------------


async def test_assign_updates_resource_incident_and_history(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, resource, _ = setup
    coordinator = headers[RoleCode.COORDINATOR]

    response = await _assign(client, coordinator, incident, resource)

    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["status"] == "resources_assigned"
    assert detail["version"] == incident["version"] + 1
    assert detail["active_assignments"] == 1
    # `resources_assigned` nunca es una acción manual.
    assert "resources_assigned" not in detail["allowed_transitions"]

    updated = await _get(client, coordinator, f"resources/{resource['id']}")
    assert updated["status"] == "in_service"
    assert updated["version"] == resource["version"] + 1
    current = updated["current_assignment"]
    assert current["incident_code"] == incident["code"]
    assert current["eta"]["origin"] == "base"

    (assignment,) = await _assignments(client, coordinator, incident)
    assert assignment["resource"]["code"] == "ASG-01"
    assert assignment["released_at"] is None
    assert assignment["eta"] == current["eta"]

    events = await _events(client, coordinator, incident)
    assert [e["event_type"] for e in events] == [
        "incident_created",
        "resource_assigned",
        "status_changed",
    ]
    assert events[1]["payload"]["resource"] == "ASG-01"
    assert events[1]["payload"]["eta"] == current["eta"]
    assert events[2]["payload"] == {
        "from": "received",
        "to": "resources_assigned",
        "cause": "assignment",
    }


async def test_eta_follows_the_approved_formula(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, resource, _ = setup
    response = await _assign(client, headers[RoleCode.COORDINATOR], incident, resource)
    assert response.status_code == 200

    (assignment,) = await _assignments(client, headers[RoleCode.COORDINATOR], incident)
    # Gijón → Oviedo: ≈ 24,6 km en línea recta * 1,4 = 34,5 km; autobomba a 50 km/h.
    assert assignment["eta"] == {"minutes": 42, "distance_km": 34.5, "origin": "base"}


async def test_stored_eta_does_not_change_when_the_base_moves(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, resource, _ = setup
    admin = headers[RoleCode.ADMIN]
    assert (await _assign(client, admin, incident, resource)).status_code == 200
    (before,) = await _assignments(client, admin, incident)
    current = await _get(client, admin, f"resources/{resource['id']}")

    moved = await client.patch(
        f"{API}/resources/{resource['id']}",
        json={"version": current["version"], "base": {"municipality": "Avilés", **AVILES}},
        headers=admin,
    )
    assert moved.status_code == 200

    (after,) = await _assignments(client, admin, incident)
    assert after["eta"] == before["eta"]


async def test_assign_without_coordinates_has_no_eta(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    _, resource, _ = setup
    admin = headers[RoleCode.ADMIN]
    incident = await _incident(client, session, admin, coordinates=None)

    assert (await _assign(client, admin, incident, resource)).status_code == 200

    (assignment,) = await _assignments(client, admin, incident)
    assert assignment["eta"] is None
    events = await _events(client, admin, incident)
    assert events[1]["payload"]["eta"] is None
    assert events[1]["payload"]["eta_unavailable"] == "incident_without_coordinates"


async def test_several_resources_per_incident(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, first, organization = setup
    admin = headers[RoleCode.ADMIN]
    second = await _resource(client, session, admin, "ASG-02", organization_id=organization)

    detail = (await _assign(client, admin, incident, first)).json()
    detail = (await _assign(client, admin, detail, second)).json()

    assert detail["active_assignments"] == 2
    # El segundo no vuelve a cambiar el estado.
    assert detail["status"] == "resources_assigned"
    listed = await _get(client, admin, "incidents")
    (item,) = [i for i in listed["items"] if i["id"] == incident["id"]]
    assert item["active_assignments"] == 2


async def test_assigning_in_progress_does_not_change_status(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, resource, _ = setup
    admin = headers[RoleCode.ADMIN]
    for target in ("assessing", "in_progress"):
        incident = (
            await client.post(
                f"{API}/incidents/{incident['id']}/status",
                json={"status": target, "version": incident["version"]},
                headers=admin,
            )
        ).json()

    detail = (await _assign(client, admin, incident, resource)).json()

    assert detail["status"] == "in_progress"
    assert [e["event_type"] for e in await _events(client, admin, incident)][-1] == (
        "resource_assigned"
    )


@pytest.mark.parametrize(
    ("prepare", "code", "status"),
    [
        ("out_of_service", "resource_not_available", 422),
        ("in_service", "resource_not_available", 422),
        ("inactive", "resource_inactive", 422),
    ],
)
async def test_only_available_active_resources_can_be_assigned(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
    prepare: str,
    code: str,
    status: int,
) -> None:
    incident, resource, _ = setup
    admin = headers[RoleCode.ADMIN]
    if prepare == "inactive":
        response = await client.patch(
            f"{API}/resources/{resource['id']}",
            json={"version": resource["version"], "is_active": False},
            headers=admin,
        )
    else:
        response = await client.post(
            f"{API}/resources/{resource['id']}/status",
            json={"status": prepare, "version": resource["version"]},
            headers=admin,
        )
    assert response.status_code == 200

    response = await _assign(client, admin, incident, resource)

    assert response.status_code == status
    assert response.json() == {"detail": code}
    assert await _assignments(client, admin, incident) == []


async def test_assign_errors(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, resource, _ = setup
    admin = headers[RoleCode.ADMIN]

    stale = await _assign(client, admin, {**incident, "version": 99}, resource)
    assert (stale.status_code, stale.json()) == (409, {"detail": "version_conflict"})

    unknown = await _assign(client, admin, incident, {"id": "00000000-0000-4000-8000-000000000000"})
    assert (unknown.status_code, unknown.json()) == (404, {"detail": "resource_not_found"})

    cancelled = (
        await client.post(
            f"{API}/incidents/{incident['id']}/status",
            json={"status": "cancelled", "version": incident["version"]},
            headers=admin,
        )
    ).json()
    closed = await _assign(client, admin, cancelled, resource)
    assert (closed.status_code, closed.json()) == (422, {"detail": "incident_closed"})


async def test_a_resource_has_one_active_assignment(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, resource, _ = setup
    admin = headers[RoleCode.ADMIN]
    other = await _incident(client, session, admin, coordinates=GIJON)
    detail = (await _assign(client, admin, incident, resource)).json()

    again = await _assign(client, admin, detail, resource)
    elsewhere = await _assign(client, admin, other, resource)

    for response in (again, elsewhere):
        assert response.status_code == 409
        assert response.json() == {"detail": "resource_already_assigned"}


# --- Llegada y retirada ---------------------------------------------------------------


async def test_arrival_does_not_change_incident_status(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    member_headers: MemberHeadersFactory,
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, resource, organization = setup
    # Operador de la organización del recurso (ámbito, CLAUDE.md §2.11, D9).
    operator = await member_headers(RoleCode.OPERATOR, organization)
    detail = (await _assign(client, headers[RoleCode.ADMIN], incident, resource)).json()
    (assignment,) = await _assignments(client, headers[RoleCode.ADMIN], incident)
    path = f"{API}/assignments/{assignment['id']}/arrival"

    # El operador puede marcar la llegada.
    response = await client.post(path, json={"version": detail["version"]}, headers=operator)

    assert response.status_code == 200, response.text
    arrived = response.json()
    assert arrived["status"] == "resources_assigned"
    assert arrived["version"] == detail["version"] + 1
    (assignment,) = await _assignments(client, headers[RoleCode.ADMIN], incident)
    assert assignment["arrived_at"] is not None
    events = await _events(client, headers[RoleCode.ADMIN], incident)
    assert events[-1]["event_type"] == "resource_arrived"

    twice = await client.post(path, json={"version": arrived["version"]}, headers=operator)
    assert twice.json() == {"detail": "assignment_already_arrived"}


@pytest.mark.parametrize(
    ("reason", "resource_status"),
    [
        ("completed", "available"),
        ("not_needed", "available"),
        ("unavailable", "out_of_service"),
    ],
)
async def test_release_with_a_reason(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
    reason: str,
    resource_status: str,
) -> None:
    incident, resource, _ = setup
    admin = headers[RoleCode.ADMIN]
    detail = (await _assign(client, admin, incident, resource)).json()
    (assignment,) = await _assignments(client, admin, incident)

    response = await client.post(
        f"{API}/assignments/{assignment['id']}/release",
        json={"version": detail["version"], "reason": reason},
        headers=admin,
    )

    assert response.status_code == 200, response.text
    released = response.json()
    # Era el último y el incidente seguía esperando: vuelve a valoración.
    assert released["status"] == "assessing"
    assert released["active_assignments"] == 0
    updated = await _get(client, admin, f"resources/{resource['id']}")
    assert updated["status"] == resource_status
    assert updated["current_assignment"] is None
    (assignment,) = await _assignments(client, admin, incident)
    assert assignment["release_reason"] == reason
    events = await _events(client, admin, incident)
    assert [e["event_type"] for e in events[-2:]] == ["resource_released", "status_changed"]
    assert events[-2]["payload"]["reason"] == reason
    assert events[-1]["payload"] == {
        "from": "resources_assigned",
        "to": "assessing",
        "cause": "assignment",
    }


async def test_release_errors(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, resource, _ = setup
    admin = headers[RoleCode.ADMIN]
    detail = (await _assign(client, admin, incident, resource)).json()
    (assignment,) = await _assignments(client, admin, incident)
    path = f"{API}/assignments/{assignment['id']}/release"

    for reason in ("reassigned", "incident_closed"):
        system = await client.post(
            path, json={"version": detail["version"], "reason": reason}, headers=admin
        )
        assert system.json() == {"detail": "invalid_release_reason"}
    invalid = await client.post(
        path, json={"version": detail["version"], "reason": "otro"}, headers=admin
    )
    assert invalid.status_code == 422
    stale = await client.post(path, json={"version": 1, "reason": "completed"}, headers=admin)
    assert stale.json() == {"detail": "version_conflict"}

    done = (
        await client.post(
            path, json={"version": detail["version"], "reason": "completed"}, headers=admin
        )
    ).json()
    again = await client.post(
        path, json={"version": done["version"], "reason": "completed"}, headers=admin
    )
    assert again.json() == {"detail": "assignment_already_released"}
    missing = await client.post(
        f"{API}/assignments/00000000-0000-4000-8000-000000000000/release",
        json={"version": 1, "reason": "completed"},
        headers=admin,
    )
    assert (missing.status_code, missing.json()) == (404, {"detail": "assignment_not_found"})


async def test_releasing_one_of_several_keeps_the_status(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, first, organization = setup
    admin = headers[RoleCode.ADMIN]
    second = await _resource(client, session, admin, "ASG-02", organization_id=organization)
    detail = (await _assign(client, admin, incident, first)).json()
    detail = (await _assign(client, admin, detail, second)).json()
    assignment = (await _assignments(client, admin, incident))[0]

    released = (
        await client.post(
            f"{API}/assignments/{assignment['id']}/release",
            json={"version": detail["version"], "reason": "not_needed"},
            headers=admin,
        )
    ).json()

    assert released["status"] == "resources_assigned"
    assert released["active_assignments"] == 1


# --- Reasignación y cierre ------------------------------------------------------------


async def test_reassign_moves_the_resource_atomically(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    origin, resource, _ = setup
    admin = headers[RoleCode.ADMIN]
    target = await _incident(client, session, admin, coordinates=AVILES)
    origin = (await _assign(client, admin, origin, resource)).json()

    response = await _assign(client, admin, target, resource, reassign=True)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resources_assigned"
    origin_now = await _get(client, admin, f"incidents/{origin['id']}")
    assert origin_now["status"] == "assessing"
    assert origin_now["version"] == origin["version"] + 1
    assert origin_now["active_assignments"] == 0
    (old,) = await _assignments(client, admin, origin)
    assert old["release_reason"] == "reassigned"
    origin_events = await _events(client, admin, origin)
    assert origin_events[-2]["payload"]["reassigned_to"] == target["code"]
    target_events = await _events(client, admin, target)
    assert target_events[1]["payload"]["reassigned_from"] == origin["code"]
    updated = await _get(client, admin, f"resources/{resource['id']}")
    assert updated["status"] == "in_service"
    assert updated["current_assignment"]["incident_code"] == target["code"]


async def test_closing_an_incident_releases_its_resources(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, first, organization = setup
    admin = headers[RoleCode.ADMIN]
    second = await _resource(client, session, admin, "ASG-02", organization_id=organization)
    detail = (await _assign(client, admin, incident, first)).json()
    detail = (await _assign(client, admin, detail, second)).json()

    response = await client.post(
        f"{API}/incidents/{incident['id']}/status",
        json={"status": "cancelled", "version": detail["version"]},
        headers=admin,
    )

    assert response.status_code == 200, response.text
    assert response.json()["active_assignments"] == 0
    for resource in (first, second):
        updated = await _get(client, admin, f"resources/{resource['id']}")
        assert updated["status"] == "available"
    assignments = await _assignments(client, admin, incident)
    assert {a["release_reason"] for a in assignments} == {"incident_closed"}
    events = await _events(client, admin, incident)
    assert [e["event_type"] for e in events[-3:]] == [
        "resource_released",
        "resource_released",
        "status_changed",
    ]
    assert events[-1]["payload"] == {"from": "resources_assigned", "to": "cancelled"}


# --- Estado y ficha del recurso asignado ------------------------------------------------


async def test_assigned_resource_status_and_activation_are_blocked(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    member_headers: MemberHeadersFactory,
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, resource, organization = setup
    operator = await member_headers(RoleCode.OPERATOR, organization)
    admin = headers[RoleCode.ADMIN]
    assert (await _assign(client, admin, incident, resource)).status_code == 200
    current = await _get(client, admin, f"resources/{resource['id']}")

    for target in ("available", "out_of_service"):
        response = await client.post(
            f"{API}/resources/{resource['id']}/status",
            json={"status": target, "version": current["version"]},
            headers=operator,
        )
        assert response.json() == {"detail": "resource_assigned"}
    deactivate = await client.patch(
        f"{API}/resources/{resource['id']}",
        json={"version": current["version"], "is_active": False},
        headers=admin,
    )
    assert deactivate.json() == {"detail": "resource_assigned"}
    # Editar el resto de la ficha sí se puede.
    renamed = await client.patch(
        f"{API}/resources/{resource['id']}",
        json={"version": current["version"], "name": "Nuevo nombre"},
        headers=admin,
    )
    assert renamed.status_code == 200


# --- Permisos ------------------------------------------------------------------------


async def test_operator_cannot_assign_or_release(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, resource, _ = setup
    operator = headers[RoleCode.OPERATOR]

    assert (await _assign(client, operator, incident, resource)).status_code == 403
    detail = (await _assign(client, headers[RoleCode.COORDINATOR], incident, resource)).json()
    (assignment,) = await _assignments(client, operator, incident)
    response = await client.post(
        f"{API}/assignments/{assignment['id']}/release",
        json={"version": detail["version"], "reason": "completed"},
        headers=operator,
    )
    assert response.status_code == 403


# --- Candidatos ------------------------------------------------------------------------


async def test_candidates_are_sorted_by_eta_without_preselection(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
) -> None:
    incident, far, organization = setup  # base en Gijón
    admin = headers[RoleCode.ADMIN]
    near = await _resource(
        client, session, admin, "ASG-02", organization_id=organization, base=OVIEDO
    )
    nowhere = await _resource(
        client, session, admin, "ASG-03", organization_id=organization, base=None
    )
    ambulance = await _resource(
        client,
        session,
        admin,
        "ASG-04",
        organization_id=organization,
        type_code="ambulance_advanced",
        base=AVILES,
    )
    busy = await _resource(client, session, admin, "ASG-05", organization_id=organization)
    other = await _incident(client, session, admin, coordinates=GIJON)
    assert (await _assign(client, admin, other, busy)).status_code == 200

    response = await client.get(
        f"{API}/incidents/{incident['id']}/assignment-candidates", headers=admin
    )

    assert response.status_code == 200, response.text
    candidates = response.json()
    codes = [c["resource"]["code"] for c in candidates]
    # Más cerca primero; sin base, al final; el asignado a otro incidente no aparece.
    assert codes[0] == near["code"]
    assert codes[-1] == nowhere["code"]
    assert busy["code"] not in codes
    minutes = [c["eta"]["minutes"] for c in candidates if c["eta"]]
    assert minutes == sorted(minutes)
    by_code = {c["resource"]["code"]: c for c in candidates}
    assert by_code[nowhere["code"]]["eta_unavailable"] == "resource_without_position"
    # Tipos sugeridos del incendio en edificio: autobomba, rescate y ambulancia avanzada.
    assert by_code[far["code"]]["suggested"] is True
    assert by_code[ambulance["code"]]["suggested"] is True
    # Nada viene marcado como elegido.
    assert all(set(c) == {"resource", "eta", "eta_unavailable", "suggested", "current_incident"}
               for c in candidates)  # fmt: skip

    with_busy = await client.get(
        f"{API}/incidents/{incident['id']}/assignment-candidates",
        params={"include_assigned": "true", "type": "fire_engine"},
        headers=admin,
    )
    busy_candidate = next(c for c in with_busy.json() if c["resource"]["code"] == busy["code"])
    assert busy_candidate["current_incident"]["code"] == other["code"]
    assert {c["resource"]["type"]["code"] for c in with_busy.json()} == {"fire_engine"}


async def test_candidates_require_both_read_permissions(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    setup: tuple[dict[str, Any], dict[str, Any], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.permissions import ROLE_PERMISSIONS, Permission

    incident, _, _ = setup
    monkeypatch.setitem(
        ROLE_PERMISSIONS,
        RoleCode.OPERATOR,
        ROLE_PERMISSIONS[RoleCode.OPERATOR] - {Permission.RESOURCES_READ},
    )
    response = await client.get(
        f"{API}/incidents/{incident['id']}/assignment-candidates",
        headers=headers[RoleCode.OPERATOR],
    )
    assert response.status_code == 403


async def test_base_coordinates_never_reach_the_logs(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    caplog: pytest.LogCaptureFixture,
) -> None:
    import logging

    caplog.set_level(logging.DEBUG)
    admin = headers[RoleCode.ADMIN]
    organization = await _org(session)
    incident = await _incident(client, session, admin)
    resource = await _resource(
        client,
        session,
        admin,
        "LOG-01",
        organization_id=organization,
        base={"latitude": 43.527713, "longitude": -5.671947},
    )
    detail = (await _assign(client, admin, incident, resource)).json()
    await client.get(f"{API}/incidents/{incident['id']}/assignment-candidates", headers=admin)
    await _assignments(client, admin, incident)
    await client.post(
        f"{API}/assignments/00000000-0000-4000-8000-000000000000/release",
        json={"version": detail["version"], "reason": "completed"},
        headers=admin,
    )

    for value in ("43.5277", "5.6719", "43.3614", "5.8494"):
        assert value not in caplog.text
