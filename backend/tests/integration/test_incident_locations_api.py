"""Ubicación de incidentes en la API (Fase 3.2): coordenadas, validación,
`location_changed`, filtro `has_coordinates` y `GET /incidents/map`."""

import logging
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import ROLE_PERMISSIONS, Permission
from app.domain.enums import RoleCode
from app.models import IncidentType
from tests.conftest import API, Headers

# Puntos simulados dentro del área de la demo, con cifras poco habituales para
# poder buscarlas en los logs.
OVIEDO = {"latitude": 43.361412, "longitude": -5.849389}
GIJON = {"latitude": 43.535713, "longitude": -5.661527}
AVILES = {"latitude": 43.554731, "longitude": -5.924829}


async def _create(
    client: AsyncClient,
    session: AsyncSession,
    headers: Headers,
    *,
    location: dict[str, Any] | None = None,
    **fields: Any,
) -> dict[str, Any]:
    type_id = (
        await session.scalars(select(IncidentType.id).where(IncidentType.code == "flood"))
    ).one()
    body = {
        "type_id": str(type_id),
        "title": "Incidente de prueba",
        "location": location or {"municipality": "Oviedo"},
        **fields,
    }
    response = await client.post(f"{API}/incidents", json=body, headers=headers)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _patch(
    client: AsyncClient, headers: Headers, incident: dict[str, Any], **fields: Any
) -> dict[str, Any]:
    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={"version": incident["version"], **fields},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


async def _events(client: AsyncClient, headers: Headers, incident_id: str) -> list[dict[str, Any]]:
    response = await client.get(f"{API}/incidents/{incident_id}/events", headers=headers)
    data: list[dict[str, Any]] = response.json()
    return data


async def _map(client: AsyncClient, headers: Headers, **params: Any) -> dict[str, Any]:
    response = await client.get(f"{API}/incidents/map", params=params, headers=headers)
    assert response.status_code == 200, response.text
    data: dict[str, Any] = response.json()
    return data


# --- Alta y validación ------------------------------------------------------------


async def test_create_with_coordinates(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(
        client,
        session,
        admin,
        location={"municipality": "Oviedo", "latitude": 43.36141249, "longitude": -5.84938871},
    )

    # Redondeadas a 6 decimales.
    assert incident["location"] == {"municipality": "Oviedo", "description": None, **OVIEDO}
    detail = (await client.get(f"{API}/incidents/{incident['id']}", headers=admin)).json()
    assert detail["location"] == incident["location"]


async def test_create_without_coordinates(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    incident = await _create(client, session, headers[RoleCode.ADMIN])
    assert (incident["location"]["latitude"], incident["location"]["longitude"]) == (None, None)


@pytest.mark.parametrize(
    ("location", "code"),
    [
        ({"latitude": 43.36}, "coordinates_incomplete"),
        ({"longitude": -5.85}, "coordinates_incomplete"),
        # Latitud y longitud intercambiadas: en rango, pero fuera de Asturias.
        ({"latitude": -5.849389, "longitude": 43.361412}, "location_out_of_area"),
        ({"latitude": 40.4168, "longitude": -3.7038}, "location_out_of_area"),
    ],
)
async def test_invalid_coordinates_are_rejected_with_a_code(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    location: dict[str, Any],
    code: str,
) -> None:
    type_id = (
        await session.scalars(select(IncidentType.id).where(IncidentType.code == "flood"))
    ).one()
    body = {
        "type_id": str(type_id),
        "title": "x",
        "location": {"municipality": "Oviedo", **location},
    }
    response = await client.post(f"{API}/incidents", json=body, headers=headers[RoleCode.ADMIN])
    assert response.status_code == 422
    assert response.json() == {"detail": code}


@pytest.mark.parametrize(
    "coordinates",
    [
        '"latitude": 91, "longitude": -5.85',
        '"latitude": 43.36, "longitude": -181',
        '"latitude": NaN, "longitude": -5.85',
        '"latitude": 43.36, "longitude": Infinity',
    ],
)
async def test_out_of_range_or_non_finite_coordinates_are_rejected(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    coordinates: str,
) -> None:
    type_id = (
        await session.scalars(select(IncidentType.id).where(IncidentType.code == "flood"))
    ).one()
    # JSON escrito a mano: `json=` no permite enviar NaN ni Infinity.
    body = (
        f'{{"type_id": "{type_id}", "title": "x",'
        f' "location": {{"municipality": "Oviedo", {coordinates}}}}}'
    )
    response = await client.post(
        f"{API}/incidents",
        content=body,
        headers={**headers[RoleCode.ADMIN], "Content-Type": "application/json"},
    )
    assert response.status_code == 422
    # La respuesta no repite los valores recibidos.
    assert "input" not in response.json()["detail"][0]


# --- Edición y `location_changed` -------------------------------------------------


async def test_changing_coordinates_records_location_changed(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin)

    updated = await _patch(client, admin, incident, location={"municipality": "Oviedo", **OVIEDO})

    assert updated["version"] == incident["version"] + 1
    assert updated["location"] == {"municipality": "Oviedo", "description": None, **OVIEDO}
    events = await _events(client, admin, incident["id"])
    assert [e["event_type"] for e in events] == ["incident_created", "location_changed"]
    assert events[1]["payload"] == {
        "fields": ["coordinates"],
        "from": {
            "municipality": "Oviedo",
            "description": None,
            "latitude": None,
            "longitude": None,
        },
        "to": {"municipality": "Oviedo", "description": None, **OVIEDO},
    }


async def test_text_and_coordinates_change_in_one_event(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin, location={"municipality": "Oviedo", **OVIEDO})

    updated = await _patch(
        client,
        admin,
        incident,
        title="Nuevo título",
        location={"municipality": "Gijón", "description": "Puerto (simulado)", **GIJON},
    )

    # Un solo incremento de versión para todo el cambio.
    assert updated["version"] == incident["version"] + 1
    events = {e["event_type"]: e["payload"] for e in await _events(client, admin, incident["id"])}
    # La ubicación ya no va en `incident_updated`.
    assert events["incident_updated"] == {"fields": ["title"]}
    assert events["location_changed"]["fields"] == ["coordinates", "description", "municipality"]
    assert events["location_changed"]["from"] == {
        "municipality": "Oviedo",
        "description": None,
        **OVIEDO,
    }


async def test_omitting_coordinates_clears_them(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin, location={"municipality": "Oviedo", **OVIEDO})

    # La ubicación se sustituye completa.
    updated = await _patch(client, admin, incident, location={"municipality": "Oviedo"})

    assert (updated["location"]["latitude"], updated["location"]["longitude"]) == (None, None)
    last = (await _events(client, admin, incident["id"]))[-1]
    assert last["payload"]["fields"] == ["coordinates"]
    assert last["payload"]["to"]["latitude"] is None


async def test_same_location_records_nothing(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin, location={"municipality": "Oviedo", **OVIEDO})

    # Mismo valor tras el redondeo y descripción vacía = sin descripción.
    updated = await _patch(
        client,
        admin,
        incident,
        location={
            "municipality": "Oviedo",
            "description": "",
            "latitude": 43.3614121,
            "longitude": -5.8493889,
        },
    )

    assert updated["version"] == incident["version"]
    assert updated["updated_at"] == incident["updated_at"]
    assert len(await _events(client, admin, incident["id"])) == 1


async def test_location_change_with_stale_version_is_rejected(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin)
    await _patch(client, admin, incident, title="Primero")

    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={"version": incident["version"], "location": {"municipality": "Gijón", **GIJON}},
        headers=admin,
    )

    assert response.status_code == 409
    detail = (await client.get(f"{API}/incidents/{incident['id']}", headers=admin)).json()
    assert detail["location"]["latitude"] is None


async def test_invalid_coordinates_in_an_update_change_nothing(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    incident = await _create(client, session, admin)

    response = await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={
            "version": incident["version"],
            "title": "No se guarda",
            "location": {"municipality": "Oviedo", "latitude": 40.4168, "longitude": -3.7038},
        },
        headers=admin,
    )

    assert response.json() == {"detail": "location_out_of_area"}
    detail = (await client.get(f"{API}/incidents/{incident['id']}", headers=admin)).json()
    assert (detail["title"], detail["version"]) == (incident["title"], incident["version"])


# --- Listado ------------------------------------------------------------------------


async def test_list_filters_by_coordinates(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    located = await _create(client, session, admin, location={"municipality": "Oviedo", **OVIEDO})
    unlocated = await _create(client, session, admin)

    async def codes(**params: Any) -> list[str]:
        response = await client.get(f"{API}/incidents", params=params, headers=admin)
        return [item["code"] for item in response.json()["items"]]

    assert await codes(has_coordinates="true") == [located["code"]]
    assert await codes(has_coordinates="false") == [unlocated["code"]]
    assert set(await codes()) == {located["code"], unlocated["code"]}


# --- Mapa -------------------------------------------------------------------------


async def test_map_returns_geojson_of_located_active_incidents(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    oviedo = await _create(
        client, session, admin, priority="low", location={"municipality": "Oviedo", **OVIEDO}
    )
    gijon = await _create(
        client, session, admin, priority="critical", location={"municipality": "Gijón", **GIJON}
    )
    await _create(client, session, admin)  # activo, sin coordenadas
    closed = await _create(client, session, admin, location={"municipality": "Avilés", **AVILES})
    response = await client.post(
        f"{API}/incidents/{closed['id']}/status",
        json={"status": "cancelled", "version": closed["version"]},
        headers=admin,
    )
    assert response.status_code == 200

    body = await _map(client, admin)

    assert body["type"] == "FeatureCollection"
    assert (body["unlocated_total"], body["truncated"]) == (1, False)
    # Más urgentes primero; el cancelado no aparece.
    assert [f["properties"]["code"] for f in body["features"]] == [gijon["code"], oviedo["code"]]
    feature = body["features"][0]
    assert feature["type"] == "Feature"
    # Orden GeoJSON: [longitud, latitud].
    assert feature["geometry"] == {
        "type": "Point",
        "coordinates": [GIJON["longitude"], GIJON["latitude"]],
    }
    assert feature["properties"] == {
        "id": gijon["id"],
        "code": gijon["code"],
        "title": gijon["title"],
        "status": "received",
        "priority": "critical",
        "type_code": "flood",
        "type_icon": gijon["type"]["icon"],
        "is_simulated": False,
    }

    # `active=false` incluye cerrados y cancelados, como en el listado.
    assert len((await _map(client, admin, active="false"))["features"]) == 3


async def test_map_applies_status_and_priority_filters(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    high = await _create(
        client, session, admin, priority="high", location={"municipality": "Oviedo", **OVIEDO}
    )
    await _create(
        client, session, admin, priority="low", location={"municipality": "Gijón", **GIJON}
    )
    await _create(client, session, admin, priority="high")  # sin coordenadas

    body = await _map(client, admin, priority="high")
    assert [f["properties"]["code"] for f in body["features"]] == [high["code"]]
    assert body["unlocated_total"] == 1

    body = await _map(client, admin, status="assessing")
    assert (body["features"], body["unlocated_total"]) == ([], 0)


async def test_map_filters_by_bbox(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> None:
    admin = headers[RoleCode.ADMIN]
    oviedo = await _create(client, session, admin, location={"municipality": "Oviedo", **OVIEDO})
    await _create(client, session, admin, location={"municipality": "Gijón", **GIJON})
    await _create(client, session, admin)  # sin coordenadas

    # Rectángulo alrededor de Oviedo (minLon,minLat,maxLon,maxLat).
    body = await _map(client, admin, bbox="-5.9,43.3,-5.8,43.4")
    assert [f["properties"]["code"] for f in body["features"]] == [oviedo["code"]]
    # El recuento de incidentes sin coordenadas no depende del rectángulo.
    assert body["unlocated_total"] == 1

    assert (await _map(client, admin, bbox="-4.5,43.0,-4.4,43.1"))["features"] == []


@pytest.mark.parametrize(
    "bbox",
    [
        "",
        "-5.9,43.3,-5.8",
        "-5.9,43.3,-5.8,43.4,1",
        "a,43.3,-5.8,43.4",
        "-5.8,43.3,-5.9,43.4",  # mínimo > máximo
        "-5.9,43.4,-5.8,43.4",  # alto nulo
        "-181,43.3,-5.8,43.4",
        "-5.9,-91,-5.8,43.4",
        "nan,43.3,-5.8,43.4",
        "-5.9,43.3,inf,43.4",
    ],
)
async def test_invalid_bbox_is_rejected(
    client: AsyncClient, headers: dict[RoleCode, Headers], bbox: str
) -> None:
    response = await client.get(
        f"{API}/incidents/map", params={"bbox": bbox}, headers=headers[RoleCode.ADMIN]
    )
    if bbox == "":
        # Vacío = sin rectángulo.
        assert response.status_code == 200
        return
    assert response.status_code == 422
    assert response.json() == {"detail": "invalid_bbox"}


async def test_map_reports_truncation(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin = headers[RoleCode.ADMIN]
    monkeypatch.setattr("app.services.incidents.MAP_FEATURE_LIMIT", 1)
    critical = await _create(
        client, session, admin, priority="critical", location={"municipality": "Gijón", **GIJON}
    )
    await _create(
        client, session, admin, priority="low", location={"municipality": "Oviedo", **OVIEDO}
    )

    body = await _map(client, admin)

    assert body["truncated"] is True
    # Se conservan los más urgentes.
    assert [f["properties"]["code"] for f in body["features"]] == [critical["code"]]


async def test_map_requires_authentication_and_permission(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert (await client.get(f"{API}/incidents/map")).status_code == 401

    monkeypatch.setitem(
        ROLE_PERMISSIONS,
        RoleCode.OPERATOR,
        ROLE_PERMISSIONS[RoleCode.OPERATOR] - {Permission.INCIDENTS_READ},
    )
    response = await client.get(f"{API}/incidents/map", headers=headers[RoleCode.OPERATOR])
    assert response.status_code == 403


# --- Seguridad: coordenadas fuera de los logs -------------------------------------


async def test_coordinates_never_reach_the_logs(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    caplog: pytest.LogCaptureFixture,
) -> None:
    admin = headers[RoleCode.ADMIN]
    caplog.set_level(logging.DEBUG)

    incident = await _create(client, session, admin, location={"municipality": "Oviedo", **OVIEDO})
    await _patch(client, admin, incident, location={"municipality": "Gijón", **GIJON})
    await client.patch(
        f"{API}/incidents/{incident['id']}",
        json={"version": 1, "location": {"municipality": "Avilés", **AVILES}},  # 409
        headers=admin,
    )
    await client.post(
        f"{API}/incidents",
        json={
            "type_id": incident["type"]["id"],
            "title": "x",
            "location": {"municipality": "x", "latitude": -5.924829, "longitude": 43.554731},
        },  # 422 fuera del área
        headers=admin,
    )
    await _map(client, admin)
    await _events(client, admin, incident["id"])

    for value in ("43.3614", "5.8493", "43.5357", "5.6615", "43.5547", "5.9248"):
        assert value not in caplog.text
