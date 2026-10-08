"""Resumen del centro de mando: KPIs con datos reales de incidentes y recursos."""

from datetime import UTC, datetime, timedelta
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import IncidentPriority, ResourceStatus, RoleCode
from app.domain.incident_rules import ACTIVE_STATUSES
from app.models import Incident, IncidentType, Organization, ResourceType
from tests.conftest import API, Headers

SUMMARY = f"{API}/dashboard/summary"


async def _incident(
    client: AsyncClient, session: AsyncSession, headers: Headers, **fields: Any
) -> dict[str, Any]:
    type_id = (
        await session.scalars(select(IncidentType.id).where(IncidentType.code == "flood"))
    ).one()
    body = {"type_id": str(type_id), "title": "x", "municipality": "Oviedo", **fields}
    response = await client.post(f"{API}/incidents", json=body, headers=headers)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _resource(
    client: AsyncClient, headers: Headers, type_id: str, organization_id: str, code: str
) -> dict[str, Any]:
    body = {
        "code": code,
        "name": code,
        "type_id": type_id,
        "organization_id": organization_id,
        "municipality": "Gijón",
    }
    response = await client.post(f"{API}/resources", json=body, headers=headers)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_all_roles_can_read_the_summary(
    client: AsyncClient, headers: dict[RoleCode, Headers]
) -> None:
    for role in RoleCode:
        assert (await client.get(SUMMARY, headers=headers[role])).status_code == 200
    assert (await client.get(SUMMARY)).status_code == 401


async def test_empty_summary_lists_every_code_with_zero(
    client: AsyncClient, headers: dict[RoleCode, Headers]
) -> None:
    body = (await client.get(SUMMARY, headers=headers[RoleCode.OPERATOR])).json()

    incidents = body["incidents"]
    assert incidents["active_total"] == 0
    assert incidents["by_priority"] == dict.fromkeys(IncidentPriority, 0)
    assert set(incidents["by_status"]) == {status.value for status in ACTIVE_STATUSES}
    assert incidents["affected_people"] == 0
    assert incidents["reported_last_24h"] == 0
    resources = body["resources"]
    assert resources == {
        "active_total": 0,
        "by_status": dict.fromkeys(ResourceStatus, 0),
        "inactive_total": 0,
    }
    assert datetime.fromisoformat(body["generated_at"]).tzinfo is not None


async def test_summary_counts_real_data(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]

    await _incident(client, session, admin, priority="critical", affected_people=4)
    await _incident(client, session, admin, priority="critical")
    assessing = await _incident(client, session, admin, priority="low", affected_people=2)
    await client.post(
        f"{API}/incidents/{assessing['id']}/status",
        json={"status": "assessing", "version": 1},
        headers=admin,
    )
    # Cancelado: no cuenta como activo, pero sí como notificado en 24 h.
    cancelled = await _incident(client, session, admin, priority="high", affected_people=50)
    await client.post(
        f"{API}/incidents/{cancelled['id']}/status",
        json={"status": "cancelled", "version": 1},
        headers=admin,
    )
    # Notificado hace dos días: activo, pero fuera de la ventana de 24 h.
    old = await _incident(client, session, admin, priority="medium")
    await session.execute(
        update(Incident)
        .where(Incident.code == old["code"])
        .values(reported_at=datetime.now(UTC) - timedelta(days=2))
    )

    organization = Organization(code="test-org", name="Organización de prueba")
    session.add(organization)
    await session.commit()
    type_id = str(
        (
            await session.scalars(select(ResourceType.id).where(ResourceType.code == "fire_engine"))
        ).one()
    )
    org_id = str(organization.id)
    await _resource(client, admin, type_id, org_id, "R-01")
    busy = await _resource(client, admin, type_id, org_id, "R-02")
    await client.post(
        f"{API}/resources/{busy['id']}/status",
        json={"status": "in_service", "version": 1},
        headers=admin,
    )
    retired = await _resource(client, admin, type_id, org_id, "R-03")
    await client.patch(
        f"{API}/resources/{retired['id']}", json={"version": 1, "is_active": False}, headers=admin
    )

    body = (await client.get(SUMMARY, headers=headers[RoleCode.COORDINATOR])).json()

    incidents = body["incidents"]
    assert incidents["active_total"] == 4
    assert incidents["by_priority"] == {"critical": 2, "high": 0, "medium": 1, "low": 1}
    assert incidents["by_status"]["received"] == 3
    assert incidents["by_status"]["assessing"] == 1
    assert "cancelled" not in incidents["by_status"]
    assert incidents["affected_people"] == 6
    assert incidents["reported_last_24h"] == 4

    assert body["resources"] == {
        "active_total": 2,
        "by_status": {"available": 1, "in_service": 1, "out_of_service": 0},
        "inactive_total": 1,
    }
