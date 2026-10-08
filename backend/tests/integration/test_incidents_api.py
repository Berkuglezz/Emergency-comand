"""API de incidentes: permisos, reglas de dominio, historial, filtros y orden.

Todo ocurre dentro de la transacción del test (se deshace al terminar).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RoleCode
from app.models import Incident, IncidentEvent, IncidentType
from tests.conftest import API, Headers


async def _type_id(session: AsyncSession, code: str) -> str:
    incident_type = (
        await session.scalars(select(IncidentType).where(IncidentType.code == code))
    ).one()
    return str(incident_type.id)


async def _create(
    client: AsyncClient,
    session: AsyncSession,
    headers: Headers,
    *,
    type_code: str = "traffic_accident",
    **fields: Any,
) -> dict[str, Any]:
    body = {
        "type_id": await _type_id(session, type_code),
        "title": "Incidente de prueba",
        "municipality": "Oviedo",
        **fields,
    }
    response = await client.post(f"{API}/incidents", json=body, headers=headers)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _status(
    client: AsyncClient, headers: Headers, incident: dict[str, Any], target: str
) -> dict[str, Any]:
    response = await client.post(
        f"{API}/incidents/{incident['id']}/status",
        json={"status": target, "version": incident["version"]},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def _events(client: AsyncClient, headers: Headers, incident_id: str) -> list[dict[str, Any]]:
    response = await client.get(f"{API}/incidents/{incident_id}/events", headers=headers)
    assert response.status_code == 200
    data: list[dict[str, Any]] = response.json()
    return data


# --- Permisos (el backend es la fuente de verdad) --------------------------------


async def test_operator_can_read_but_never_write(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    incident = await _create(client, session, headers[RoleCode.COORDINATOR])
    operator = headers[RoleCode.OPERATOR]
    path = f"{API}/incidents/{incident['id']}"

    for read in (f"{API}/incidents", path, f"{path}/events", f"{API}/incident-types"):
        assert (await client.get(read, headers=operator)).status_code == 200, read

    type_id = await _type_id(session, "flood")
    writes = [
        ("POST", f"{API}/incidents", {"type_id": type_id, "title": "x", "municipality": "Gijón"}),
        ("PATCH", path, {"version": 1, "title": "cambio"}),
        ("POST", f"{path}/status", {"status": "assessing", "version": 1}),
        ("POST", f"{path}/status", {"status": "cancelled", "version": 1}),
        ("POST", f"{path}/notes", {"text": "nota"}),
    ]
    for method, url, body in writes:
        response = await client.request(method, url, json=body, headers=operator)
        assert response.status_code == 403, (method, url)
        assert response.json() == {"detail": "permission_denied"}

    # Nada ha cambiado ni se ha registrado.
    assert len(await _events(client, operator, incident["id"])) == 1
    detail = (await client.get(path, headers=operator)).json()
    assert (detail["version"], detail["status"], detail["title"]) == (
        1,
        "received",
        "Incidente de prueba",
    )


@pytest.mark.parametrize("role", [RoleCode.ADMIN, RoleCode.COORDINATOR])
async def test_admin_and_coordinator_can_write_and_close(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers], role: RoleCode
) -> None:
    incident = await _create(client, session, headers[role])
    incident = await _status(client, headers[role], incident, "cancelled")
    assert incident["status"] == "cancelled"


# --- Alta -------------------------------------------------------------------------


async def test_create_incident(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    incident = await _create(
        client,
        session,
        headers[RoleCode.COORDINATOR],
        type_code="flood",
        details={"water_level_cm": 35},
        affected_people=4,
        location_description="Zona baja (ubicación simulada)",
    )

    assert incident["code"].startswith("INC-")
    assert incident["status"] == "received"
    assert incident["priority"] == "medium"  # prioridad por defecto del tipo
    assert incident["type"]["code"] == "flood"
    assert incident["details"] == {"water_level_cm": 35}
    assert incident["version"] == 1
    assert incident["is_simulated"] is False
    assert incident["closed_at"] is None

    events = await _events(client, headers[RoleCode.COORDINATOR], incident["id"])
    assert [event["event_type"] for event in events] == ["incident_created"]
    assert events[0]["payload"] == {
        "status": "received",
        "priority": "medium",
        "type": "flood",
        "parent": None,
    }
    assert events[0]["actor"]["full_name"] == "Usuario coordinator"


async def test_explicit_priority_overrides_type_default(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    incident = await _create(client, session, headers[RoleCode.ADMIN], priority="critical")
    assert incident["priority"] == "critical"


@pytest.mark.parametrize(
    ("type_code", "fields", "code"),
    [
        ("flood", {"details": {"water_level_cm": -1}}, "invalid_details"),
        ("flood", {"details": {"unknown": 1}}, "invalid_details"),
        ("traffic_accident", {"details": {"anything": 1}}, "details_not_allowed"),
    ],
)
async def test_details_are_validated_per_type(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    type_code: str,
    fields: dict[str, Any],
    code: str,
) -> None:
    body = {
        "type_id": await _type_id(session, type_code),
        "title": "x",
        "municipality": "Oviedo",
        **fields,
    }
    response = await client.post(f"{API}/incidents", json=body, headers=headers[RoleCode.ADMIN])
    assert response.status_code == 422
    assert response.json() == {"detail": code}


async def test_unknown_incident_type_is_rejected(
    client: AsyncClient, headers: dict[RoleCode, Headers]
) -> None:
    body = {"type_id": str(uuid.uuid4()), "title": "x", "municipality": "Oviedo"}
    response = await client.post(f"{API}/incidents", json=body, headers=headers[RoleCode.ADMIN])
    assert response.json() == {"detail": "incident_type_not_found"}


# --- Estados ----------------------------------------------------------------------


async def test_full_lifecycle_with_reopening(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    coordinator = headers[RoleCode.COORDINATOR]
    incident = await _create(client, session, coordinator)

    assert incident["allowed_transitions"] == ["assessing", "cancelled"]
    for target in ("assessing", "in_progress", "controlled", "in_progress", "controlled", "closed"):
        incident = await _status(client, coordinator, incident, target)
        assert incident["status"] == target

    assert incident["allowed_transitions"] == []

    assert incident["closed_at"] is not None
    assert incident["version"] == 7
    changes = [
        (event["payload"]["from"], event["payload"]["to"])
        for event in await _events(client, coordinator, incident["id"])
        if event["event_type"] == "status_changed"
    ]
    assert changes == [
        ("received", "assessing"),
        ("assessing", "in_progress"),
        ("in_progress", "controlled"),
        ("controlled", "in_progress"),
        ("in_progress", "controlled"),
        ("controlled", "closed"),
    ]


@pytest.mark.parametrize(
    ("path", "target"),
    [
        ([], "in_progress"),  # no se puede saltar `assessing`
        ([], "resources_assigned"),  # inalcanzable en la Fase 2
        (["assessing", "in_progress", "controlled"], "cancelled"),
        (["cancelled"], "assessing"),  # estado terminal
        ([], "received"),  # mismo estado
    ],
)
async def test_invalid_transitions_are_rejected(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    path: list[str],
    target: str,
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin)
    for step in path:
        incident = await _status(client, admin, incident, step)
    events_before = len(await _events(client, admin, incident["id"]))

    response = await client.post(
        f"{API}/incidents/{incident['id']}/status",
        json={"status": target, "version": incident["version"]},
        headers=admin,
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "invalid_transition"}
    assert len(await _events(client, admin, incident["id"])) == events_before


async def test_status_reason_is_recorded(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin)
    await client.post(
        f"{API}/incidents/{incident['id']}/status",
        json={"status": "cancelled", "version": 1, "reason": "Aviso duplicado"},
        headers=admin,
    )
    last = (await _events(client, admin, incident["id"]))[-1]
    assert last["payload"] == {"from": "received", "to": "cancelled", "reason": "Aviso duplicado"}


# --- Versiones (bloqueo optimista) ---------------------------------------------------


async def test_stale_version_is_rejected_without_side_effects(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin)
    path = f"{API}/incidents/{incident['id']}"
    # Dos clientes leen la versión 1; el primero guarda.
    first = await client.patch(path, json={"version": 1, "title": "Primero"}, headers=admin)
    assert first.status_code == 200
    assert first.json()["version"] == 2

    for method, url, body in [
        ("PATCH", path, {"version": 1, "title": "Segundo"}),
        ("POST", f"{path}/status", {"status": "assessing", "version": 1}),
    ]:
        response = await client.request(method, url, json=body, headers=admin)
        assert response.status_code == 409
        assert response.json() == {"detail": "version_conflict"}

    detail = (await client.get(path, headers=admin)).json()
    assert (detail["title"], detail["status"], detail["version"]) == ("Primero", "received", 2)
    assert [e["event_type"] for e in await _events(client, admin, incident["id"])] == [
        "incident_created",
        "incident_updated",
    ]


# --- Edición ---------------------------------------------------------------------


async def test_update_records_one_event_per_kind_of_change(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin, type_code="wildfire")

    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={
            "version": 1,
            "priority": "critical",
            "title": "Incendio de vegetación (simulación)",
            "affected_people": 3,
            "details": {"affected_hectares": "2.5", "vegetation": "scrub"},
        },
        headers=admin,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 2
    assert body["priority"] == "critical"
    assert body["details"] == {"affected_hectares": "2.5", "vegetation": "scrub"}
    events = {e["event_type"]: e["payload"] for e in await _events(client, admin, incident["id"])}
    assert events["priority_changed"] == {"from": "high", "to": "critical"}
    assert events["incident_updated"] == {"fields": ["affected_people", "details", "title"]}


async def test_update_without_changes_records_nothing(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin)

    for body in (
        {"version": 1, "title": incident["title"], "priority": incident["priority"]},
        {"version": 1},
    ):
        response = await client.patch(f"{API}/incidents/{incident['id']}", json=body, headers=admin)
        assert response.status_code == 200
        assert response.json()["version"] == 1
        assert response.json()["updated_at"] == incident["updated_at"]

    assert len(await _events(client, admin, incident["id"])) == 1


@pytest.mark.parametrize(
    ("body", "code"),
    [({"title": None}, "field_not_nullable"), ({"details": None}, "field_not_nullable")],
)
async def test_required_fields_cannot_be_cleared(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    body: dict[str, Any],
    code: str,
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin)
    response = await client.patch(
        f"{API}/incidents/{incident['id']}", json={"version": 1, **body}, headers=admin
    )
    assert response.status_code == 422
    assert response.json() == {"detail": code}


async def test_closed_incidents_cannot_be_edited_but_accept_notes(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin)
    incident = await _status(client, admin, incident, "cancelled")
    path = f"{API}/incidents/{incident['id']}"

    response = await client.patch(
        path, json={"version": incident["version"], "title": "x"}, headers=admin
    )
    assert response.json() == {"detail": "incident_closed"}

    note = await client.post(f"{path}/notes", json={"text": "Cierre revisado"}, headers=admin)
    assert note.status_code == 201
    # Las notas no modifican datos operativos: la versión no cambia.
    assert (await client.get(path, headers=admin)).json()["version"] == incident["version"]


# --- Jerarquía (un único nivel) ---------------------------------------------------


async def test_parent_and_children(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    parent = await _create(client, session, admin, type_code="severe_weather", title="Temporal")
    child = await _create(client, session, admin, parent_incident_id=parent["id"], title="Hijo")

    detail = (await client.get(f"{API}/incidents/{parent['id']}", headers=admin)).json()
    assert [c["code"] for c in detail["children"]] == [child["code"]]
    assert child["parent"]["code"] == parent["code"]

    # Un hijo no puede ser padre de otro incidente (un solo nivel).
    body = {
        "type_id": await _type_id(session, "flood"),
        "title": "Nieto",
        "municipality": "Avilés",
        "parent_incident_id": child["id"],
    }
    response = await client.post(f"{API}/incidents", json=body, headers=admin)
    assert response.json() == {"detail": "invalid_parent"}

    # Un incidente con hijos no puede convertirse en hijo.
    other = await _create(client, session, admin)
    response = await client.patch(
        f"{API}/incidents/{parent['id']}",
        json={"version": parent["version"], "parent_incident_id": other["id"]},
        headers=admin,
    )
    assert response.json() == {"detail": "invalid_parent"}

    # Un incidente no puede ser su propio padre.
    response = await client.patch(
        f"{API}/incidents/{other['id']}",
        json={"version": other["version"], "parent_incident_id": other["id"]},
        headers=admin,
    )
    assert response.json() == {"detail": "invalid_parent"}


async def test_closing_a_parent_does_not_close_its_children(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    parent = await _create(client, session, admin)
    child = await _create(client, session, admin, parent_incident_id=parent["id"])

    parent = await _status(client, admin, parent, "cancelled")

    assert parent["status"] == "cancelled"
    child_now = (await client.get(f"{API}/incidents/{child['id']}", headers=admin)).json()
    assert child_now["status"] == "received"


async def test_parent_change_is_recorded(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    parent = await _create(client, session, admin)
    incident = await _create(client, session, admin)

    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={"version": 1, "parent_incident_id": parent["id"]},
        headers=admin,
    )
    assert response.json()["parent"]["code"] == parent["code"]
    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={"version": 2, "parent_incident_id": None},
        headers=admin,
    )
    assert response.json()["parent"] is None

    changes = [
        e["payload"]
        for e in await _events(client, admin, incident["id"])
        if e["event_type"] == "parent_changed"
    ]
    assert changes == [{"from": None, "to": parent["code"]}, {"from": parent["code"], "to": None}]


async def test_one_edit_increments_version_once(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    # Regresión: validar el padre (consulta) no debe provocar un UPDATE intermedio.
    admin = headers[RoleCode.ADMIN]
    parent = await _create(client, session, admin)
    incident = await _create(client, session, admin)

    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={
            "version": 1,
            "priority": "critical",
            "parent_incident_id": parent["id"],
            "title": "Otro título",
        },
        headers=admin,
    )

    assert response.status_code == 200, response.text
    assert response.json()["version"] == 2


# --- Notas e historial ------------------------------------------------------------


async def test_notes_and_timeline_order(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin)
    path = f"{API}/incidents/{incident['id']}"

    note = await client.post(f"{path}/notes", json={"text": "Primera valoración"}, headers=admin)
    assert note.status_code == 201
    assert note.json()["payload"] == {"text": "Primera valoración"}
    await _status(client, admin, incident, "assessing")
    await client.post(f"{path}/notes", json={"text": "Segunda nota"}, headers=admin)

    events = await _events(client, admin, incident["id"])
    assert [e["event_type"] for e in events] == [
        "incident_created",
        "note_added",
        "status_changed",
        "note_added",
    ]
    times = [e["occurred_at"] for e in events]
    assert times == sorted(times)

    empty = await client.post(f"{path}/notes", json={"text": "   "}, headers=admin)
    assert empty.status_code == 422


async def test_unknown_incident_returns_404(
    client: AsyncClient, headers: dict[RoleCode, Headers]
) -> None:
    missing = f"{API}/incidents/{uuid.uuid4()}"
    for url in (missing, f"{missing}/events"):
        response = await client.get(url, headers=headers[RoleCode.ADMIN])
        assert response.status_code == 404
        assert response.json() == {"detail": "incident_not_found"}


# --- Listado: filtros, orden y paginación ----------------------------------------


async def _listing(client: AsyncClient, headers: Headers, **params: Any) -> tuple[list[str], int]:
    response = await client.get(f"{API}/incidents", params=params, headers=headers)
    assert response.status_code == 200, response.text
    body = response.json()
    return [item["title"] for item in body["items"]], body["total"]


async def test_filters(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    tag = uuid.uuid4().hex[:8]  # aísla este test de otros incidentes
    a = await _create(client, session, admin, title=f"{tag} A", priority="critical")
    await _create(client, session, admin, title=f"{tag} B", type_code="flood", priority="low")
    c = await _create(client, session, admin, title=f"{tag} C 100%")
    await _status(client, admin, c, "cancelled")

    assert await _listing(client, admin, q=tag) == ([f"{tag} A", f"{tag} B"], 2)
    assert (await _listing(client, admin, q=tag, active="false"))[1] == 3
    assert (await _listing(client, admin, q=tag, priority="critical"))[0] == [f"{tag} A"]
    assert (await _listing(client, admin, q=tag, type="flood"))[0] == [f"{tag} B"]
    assert (await _listing(client, admin, q=tag, status=["received"], priority=["low"]))[0] == [
        f"{tag} B"
    ]
    # La búsqueda escapa los comodines de LIKE.
    assert (await _listing(client, admin, q=f"{tag} C 100%", active="false"))[0] == [
        f"{tag} C 100%"
    ]
    assert (await _listing(client, admin, q=a["code"]))[0] == [f"{tag} A"]


async def test_filter_by_parent(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    parent = await _create(client, session, admin)
    await _create(client, session, admin, parent_incident_id=parent["id"], title="hijo-1")
    await _create(client, session, admin, parent_incident_id=parent["id"], title="hijo-2")

    titles, total = await _listing(client, admin, parent_id=parent["id"], sort="reported_at")
    assert total == 2
    assert sorted(titles) == ["hijo-1", "hijo-2"]


async def test_sorting_uses_the_requested_field_with_id_as_tiebreak(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    tag = uuid.uuid4().hex[:8]
    created = {
        name: await _create(client, session, admin, title=f"{tag} {name}", priority=priority)
        for name, priority in [("w", "low"), ("x", "critical"), ("y", "medium"), ("z", "critical")]
    }
    # Fechas controladas: x y z comparten `reported_at` (empate → desempata `id`).
    base = datetime(2026, 1, 1, tzinfo=UTC)
    reported = {"w": base + timedelta(hours=3), "x": base, "y": base + timedelta(hours=1)}
    reported["z"] = reported["x"]
    updated = {"w": base, "x": base + timedelta(hours=2), "y": base + timedelta(hours=5)}
    updated["z"] = base + timedelta(hours=1)
    for name, incident in created.items():
        await session.execute(
            update(Incident)
            .where(Incident.id == uuid.UUID(incident["id"]))
            .values(reported_at=reported[name], updated_at=updated[name])
            .execution_options(synchronize_session=False)
        )
    await session.commit()
    ids = {name: uuid.UUID(incident["id"]) for name, incident in created.items()}
    x_first, z_first = sorted(["x", "z"], key=lambda name: ids[name])

    def names(titles: list[str]) -> list[str]:
        return [title.split()[-1] for title in titles]

    asc = names((await _listing(client, admin, q=tag, sort="reported_at"))[0])
    assert asc == [x_first, z_first, "y", "w"]
    desc = names((await _listing(client, admin, q=tag, sort="-reported_at"))[0])
    assert desc == ["w", "y", z_first, x_first]
    by_update = names((await _listing(client, admin, q=tag, sort="-updated_at"))[0])
    assert by_update == ["y", "x", "z", "w"]
    # Prioridad: críticas primero (empate en fecha → id), luego media y baja.
    by_priority = names((await _listing(client, admin, q=tag, sort="priority"))[0])
    assert by_priority == [z_first, x_first, "y", "w"]


async def test_pagination(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    tag = uuid.uuid4().hex[:8]
    for index in range(5):
        await _create(client, session, admin, title=f"{tag} {index}")

    page1, total = await _listing(client, admin, q=tag, sort="reported_at", limit=2, offset=0)
    page2, _ = await _listing(client, admin, q=tag, sort="reported_at", limit=2, offset=2)
    page3, _ = await _listing(client, admin, q=tag, sort="reported_at", limit=2, offset=4)

    assert total == 5
    assert (len(page1), len(page2), len(page3)) == (2, 2, 1)
    assert len(set(page1 + page2 + page3)) == 5
    assert (
        await client.get(f"{API}/incidents", params={"limit": 101}, headers=admin)
    ).status_code == 422


async def test_incident_types_catalog(
    client: AsyncClient, headers: dict[RoleCode, Headers]
) -> None:
    response = await client.get(f"{API}/incident-types", headers=headers[RoleCode.OPERATOR])
    types = {t["code"]: t for t in response.json()}

    assert len(types) == 10
    assert types["wildfire"]["details_schema_key"] == "wildfire"
    assert types["hazmat"]["default_priority"] == "critical"
    assert "fire_engine" in types["wildfire"]["suggested_resource_types"]


async def test_events_are_never_exposed_for_writing(
    session: AsyncSession, client: AsyncClient, headers: dict[RoleCode, Headers]
) -> None:
    # No hay endpoints de edición o borrado del historial.
    incident = await _create(client, session, headers[RoleCode.ADMIN])
    events_path = f"{API}/incidents/{incident['id']}/events"
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        response = await client.request(method, events_path, headers=headers[RoleCode.ADMIN])
        assert response.status_code == 405
    count = len((await session.scalars(select(IncidentEvent))).all())
    assert count >= 1
