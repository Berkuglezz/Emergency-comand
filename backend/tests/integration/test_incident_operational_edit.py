"""Edición operativa y prioridad inicial (CLAUDE.md §2.11, R.2 y D6).

El operador solo modifica descripción, personas afectadas, ubicación y
`details`, y crea incidentes con la prioridad por defecto del tipo. Las
peticiones se envían directamente a la API, como haría un cliente
manipulado: el backend debe rechazarlas enteras, sin cambios parciales ni
eventos.
"""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
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
    client: AsyncClient, session: AsyncSession, headers: Headers, **fields: Any
) -> dict[str, Any]:
    body = {
        "type_id": await _type_id(session, "flood"),
        "title": "Inundación de prueba",
        "description": "Descripción inicial",
        "location": {"municipality": "Oviedo"},
        **fields,
    }
    response = await client.post(f"{API}/incidents", json=body, headers=headers)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _snapshot(
    client: AsyncClient, headers: Headers, incident_id: str
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    detail = (await client.get(f"{API}/incidents/{incident_id}", headers=headers)).json()
    events = (await client.get(f"{API}/incidents/{incident_id}/events", headers=headers)).json()
    return detail, events


# --- Edición operativa del operador -------------------------------------------------


async def test_operator_edits_operational_fields(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    incident = await _create(client, session, headers[RoleCode.COORDINATOR])
    operator = headers[RoleCode.OPERATOR]

    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={
            "version": incident["version"],
            "description": "Agua en la planta baja",
            "affected_people": 3,
            "location": {"municipality": "Siero", "latitude": 43.39, "longitude": -5.66},
            "details": {"water_level_cm": 40},
        },
        headers=operator,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["version"] == incident["version"] + 1
    assert data["description"] == "Agua en la planta baja"
    assert data["affected_people"] == 3
    assert data["location"]["municipality"] == "Siero"
    assert data["details"] == {"water_level_cm": 40}
    # Lo que no es operativo sigue igual.
    assert (data["priority"], data["title"]) == (incident["priority"], incident["title"])
    _, events = await _snapshot(client, operator, incident["id"])
    assert [event["event_type"] for event in events][-2:] == [
        "incident_updated",
        "location_changed",
    ]


@pytest.mark.parametrize(
    "forbidden",
    [
        pytest.param({"priority": "critical"}, id="prioridad"),
        pytest.param({"title": "Título cambiado"}, id="titulo"),
        pytest.param({"parent_incident_id": None}, id="padre"),
        # Mezclado con campos permitidos: no se aplica nada de la petición.
        pytest.param(
            {"description": "Cambio permitido", "affected_people": 9, "priority": "low"},
            id="mezcla",
        ),
    ],
)
async def test_operator_cannot_touch_non_operational_fields(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    forbidden: dict[str, Any],
) -> None:
    incident = await _create(client, session, headers[RoleCode.COORDINATOR])
    operator = headers[RoleCode.OPERATOR]
    before = await _snapshot(client, operator, incident["id"])

    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={"version": incident["version"], **forbidden},
        headers=operator,
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "field_not_permitted"}
    # Sin cambios parciales, sin `version` nueva y sin eventos.
    assert await _snapshot(client, operator, incident["id"]) == before


async def test_operator_cannot_resend_the_current_priority(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    """Cuenta lo enviado, no lo que cambiaría: ni siquiera el mismo valor."""
    incident = await _create(client, session, headers[RoleCode.COORDINATOR])

    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={"version": incident["version"], "priority": incident["priority"]},
        headers=headers[RoleCode.OPERATOR],
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "field_not_permitted"}


async def test_the_type_can_never_be_changed(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    incident = await _create(client, session, headers[RoleCode.COORDINATOR])
    for role in (RoleCode.OPERATOR, RoleCode.COORDINATOR):
        response = await client.patch(
            f"{API}/incidents/{incident['id']}",
            json={"version": incident["version"], "type_id": await _type_id(session, "hazmat")},
            headers=headers[role],
        )
        assert response.status_code == 422, role


# --- Prioridad inicial ----------------------------------------------------------------


async def test_operator_gets_the_default_priority_of_each_type(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    types = (
        await session.scalars(select(IncidentType).where(IncidentType.is_active.is_(True)))
    ).all()
    assert types
    for incident_type in types:
        body = {
            "type_id": str(incident_type.id),
            "title": f"Aviso {incident_type.code}",
            "location": {"municipality": "Avilés"},
        }
        response = await client.post(
            f"{API}/incidents", json=body, headers=headers[RoleCode.OPERATOR]
        )
        if response.status_code == 422:
            # Tipos con `details` obligatorios: no es una cuestión de prioridad.
            assert response.json()["detail"] == "invalid_details", incident_type.code
            continue
        assert response.status_code == 201, (incident_type.code, response.text)
        assert response.json()["priority"] == incident_type.default_priority


@pytest.mark.parametrize("priority", ["critical", "low", None])
async def test_operator_cannot_choose_the_initial_priority(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    priority: str | None,
) -> None:
    count = await session.scalar(select(func.count()).select_from(Incident))
    body = {
        "type_id": await _type_id(session, "flood"),
        "title": "Aviso con prioridad",
        "location": {"municipality": "Gijón"},
        "priority": priority,
    }

    response = await client.post(f"{API}/incidents", json=body, headers=headers[RoleCode.OPERATOR])

    if priority is None:
        # `null` explícito equivale a no indicarla: prioridad por defecto del tipo.
        assert response.status_code == 201
        assert response.json()["priority"] == "medium"
    else:
        assert response.status_code == 403
        assert response.json() == {"detail": "field_not_permitted"}
        assert await session.scalar(select(func.count()).select_from(Incident)) == count


# --- Incidente padre en el alta (D11) -------------------------------------------------


async def _counts(session: AsyncSession) -> tuple[int | None, int | None]:
    return (
        await session.scalar(select(func.count()).select_from(Incident)),
        await session.scalar(select(func.count()).select_from(IncidentEvent)),
    )


async def test_operator_cannot_create_a_child_incident(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    parent = await _create(client, session, headers[RoleCode.COORDINATOR])
    operator = headers[RoleCode.OPERATOR]
    before_parent = await _snapshot(client, operator, parent["id"])
    before_counts = await _counts(session)

    response = await client.post(
        f"{API}/incidents",
        json={
            "type_id": await _type_id(session, "flood"),
            "title": "Hijo del operador",
            "location": {"municipality": "Gijón"},
            "parent_incident_id": parent["id"],
        },
        headers=operator,
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "field_not_permitted"}
    # No se crea el incidente, no hay eventos y el padre sigue sin hijos.
    assert await _counts(session) == before_counts
    after_parent = await _snapshot(client, operator, parent["id"])
    assert after_parent == before_parent
    assert after_parent[0]["children"] == []


async def test_operator_creates_without_parent(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    created = await _create(client, session, headers[RoleCode.OPERATOR], parent_incident_id=None)
    assert created["parent"] is None


@pytest.mark.parametrize("role", [RoleCode.ADMIN, RoleCode.COORDINATOR])
async def test_admin_and_coordinator_create_child_incidents(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers], role: RoleCode
) -> None:
    parent = await _create(client, session, headers[role])
    child = await _create(client, session, headers[role], parent_incident_id=parent["id"])
    assert child["parent"]["id"] == parent["id"]


# --- Coordinador y admin: sin cambios --------------------------------------------------


@pytest.mark.parametrize("role", [RoleCode.ADMIN, RoleCode.COORDINATOR])
async def test_full_edit_and_initial_priority_are_kept(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers], role: RoleCode
) -> None:
    incident = await _create(client, session, headers[role], priority="critical")
    assert incident["priority"] == "critical"

    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={
            "version": incident["version"],
            "priority": "low",
            "title": "Título revisado",
            "description": "Revisado",
        },
        headers=headers[role],
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert (data["priority"], data["title"], data["description"]) == (
        "low",
        "Título revisado",
        "Revisado",
    )
