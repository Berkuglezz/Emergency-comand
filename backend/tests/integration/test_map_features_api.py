"""Mapa operativo, M.1 (CLAUDE.md §2.12): perímetros de un incidente en PostGIS.

Crear, consultar, editar y retirar; historial con la geometría anterior y la
nueva (D-M3); retirar sin borrar (D-M4); «no validado» (D-M5); versión propia
(D-M7); permisos (D-M2); incidentes cerrados; geometrías inválidas rechazadas
sin repetir la entrada ni escribirla en logs.
"""

import logging
import math
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import RoleCode
from app.domain.map_features import MAX_POLYGON_VERTICES, MAX_RING_POSITIONS_INPUT
from app.models import IncidentEvent, IncidentMapFeature, IncidentType
from tests.conftest import API, Headers

# Cuadrado de ~1 km en Oviedo, [lon, lat], cerrado; y una versión desplazada.
SQUARE = [[-5.86, 43.36], [-5.85, 43.36], [-5.85, 43.37], [-5.86, 43.37], [-5.86, 43.36]]
MOVED = [[-5.87, 43.36], [-5.85, 43.36], [-5.85, 43.38], [-5.87, 43.38], [-5.87, 43.36]]
# Valores distintivos para comprobar que nunca llegan a los logs.
LEAK = [
    [-5.861357, 43.362468],
    [-5.851357, 43.362468],
    [-5.851357, 43.372468],
    [-5.861357, 43.372468],
    [-5.861357, 43.362468],
]


def _polygon(ring: list[list[float]]) -> dict[str, Any]:
    return {"type": "Polygon", "coordinates": [ring]}


async def _incident(client: AsyncClient, session: AsyncSession, headers: Headers) -> dict[str, Any]:
    type_id = (
        await session.scalars(select(IncidentType.id).where(IncidentType.code == "wildfire"))
    ).one()
    response = await client.post(
        f"{API}/incidents",
        json={
            "type_id": str(type_id),
            "title": "Incendio con perímetro",
            "location": {"municipality": "Oviedo", "latitude": 43.3614, "longitude": -5.8494},
            "details": {"affected_hectares": "12.5", "vegetation": "forest"},
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def _create(client: AsyncClient, headers: Headers, incident_id: str, **body: Any) -> Any:
    return await client.post(
        f"{API}/incidents/{incident_id}/map-features",
        json={"kind": "perimeter", "geometry": _polygon(SQUARE), **body},
        headers=headers,
    )


async def _features(
    client: AsyncClient, headers: Headers, incident_id: str, *, include_retired: bool = False
) -> list[dict[str, Any]]:
    response = await client.get(
        f"{API}/incidents/{incident_id}/map-features",
        params={"include_retired": str(include_retired).lower()},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["type"] == "FeatureCollection"
    features: list[dict[str, Any]] = response.json()["features"]
    return features


async def _events(client: AsyncClient, headers: Headers, incident_id: str) -> list[dict[str, Any]]:
    response = await client.get(f"{API}/incidents/{incident_id}/events", headers=headers)
    events: list[dict[str, Any]] = response.json()
    return [event for event in events if event["event_type"].startswith("map_feature")]


async def _counts(session: AsyncSession) -> tuple[int | None, int | None]:
    return (
        await session.scalar(select(func.count()).select_from(IncidentMapFeature)),
        await session.scalar(select(func.count()).select_from(IncidentEvent)),
    )


@pytest.fixture
async def incident(
    client: AsyncClient, session: AsyncSession, headers: dict[RoleCode, Headers]
) -> dict[str, Any]:
    return await _incident(client, session, headers[RoleCode.COORDINATOR])


# --- Ciclo completo ------------------------------------------------------------------


async def test_perimeter_lifecycle_is_persisted_and_audited(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    incident: dict[str, Any],
) -> None:
    coordinator = headers[RoleCode.COORDINATOR]
    incident_id = incident["id"]

    # Crear.
    created = await _create(client, coordinator, incident_id, label="Frente norte")
    assert created.status_code == 201, created.text
    feature = created.json()
    feature_id = feature["id"]
    props = feature["properties"]
    assert feature["type"] == "Feature"
    assert feature["geometry"] == _polygon(SQUARE)
    assert (props["kind"], props["status"], props["verification"], props["version"]) == (
        "perimeter",
        "active",
        "unverified",
        1,
    )
    assert props["created_by"]["full_name"] == "Usuario coordinator"
    assert props["label"] == "Frente norte"

    # Persistido en PostGIS: polígono válido WGS84 con 4 vértices.
    row = (
        await session.execute(
            text(
                "SELECT GeometryType(geom) AS type, ST_SRID(geom) AS srid,"
                " ST_IsValid(geom) AS valid, ST_NPoints(geom) AS points"
                " FROM incident_map_features WHERE id = :id"
            ),
            {"id": feature_id},
        )
    ).one()
    assert (row.type, row.srid, row.valid, row.points) == ("POLYGON", 4326, True, 5)

    # Consultar (se vuelve a cargar desde la base de datos).
    (listed,) = await _features(client, headers[RoleCode.OPERATOR], incident_id)
    assert listed == feature

    # Editar la geometría.
    edited = await client.patch(
        f"{API}/map-features/{feature_id}",
        json={"version": 1, "geometry": _polygon(MOVED)},
        headers=coordinator,
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["geometry"] == _polygon(MOVED)
    assert edited.json()["properties"]["version"] == 2

    # Editar solo la etiqueta.
    relabeled = await client.patch(
        f"{API}/map-features/{feature_id}",
        json={"version": 2, "label": "Frente norte (revisado)"},
        headers=headers[RoleCode.ADMIN],
    )
    assert relabeled.status_code == 200, relabeled.text
    assert relabeled.json()["properties"]["version"] == 3
    assert relabeled.json()["properties"]["updated_by"]["full_name"] == "Usuario admin"

    # Retirar: no se borra.
    retired = await client.post(
        f"{API}/map-features/{feature_id}/retire",
        json={"version": 3, "reason": "Perímetro superado"},
        headers=coordinator,
    )
    assert retired.status_code == 200, retired.text
    retired_props = retired.json()["properties"]
    assert (retired_props["status"], retired_props["version"]) == ("retired", 4)
    assert retired_props["retire_reason"] == "Perímetro superado"
    assert retired_props["retired_at"] is not None
    assert await _features(client, coordinator, incident_id) == []
    assert [
        f["id"] for f in await _features(client, coordinator, incident_id, include_retired=True)
    ] == [feature_id]
    assert (
        await session.scalar(
            select(func.count()).where(IncidentMapFeature.id == uuid.UUID(feature_id))
        )
        == 1
    )

    # Historial: un evento por cambio, con la geometría anterior y la nueva.
    events = await _events(client, coordinator, incident_id)
    assert [e["event_type"] for e in events] == [
        "map_feature_added",
        "map_feature_updated",
        "map_feature_updated",
        "map_feature_retired",
    ]
    added, geometry_change, label_change, retirement = (e["payload"] for e in events)
    assert (added["before"], added["after"]) == (None, _polygon(SQUARE))
    assert (geometry_change["before"], geometry_change["after"]) == (
        _polygon(SQUARE),
        _polygon(MOVED),
    )
    assert geometry_change["fields"] == ["geometry"]
    assert label_change["fields"] == ["label"]
    assert label_change["before"] == label_change["after"] == _polygon(MOVED)
    assert (retirement["before"], retirement["after"]) == (_polygon(MOVED), None)
    assert retirement["reason"] == "Perímetro superado"
    assert {e["payload"]["feature_id"] for e in events} == {feature_id}
    assert [e["actor"]["full_name"] for e in events] == [
        "Usuario coordinator",
        "Usuario coordinator",
        "Usuario admin",
        "Usuario coordinator",
    ]

    # D-M7: el incidente no cambia de versión por sus geometrías.
    detail = (await client.get(f"{API}/incidents/{incident_id}", headers=coordinator)).json()
    assert detail["version"] == incident["version"]


async def test_edit_without_changes_writes_nothing(
    client: AsyncClient, headers: dict[RoleCode, Headers], incident: dict[str, Any]
) -> None:
    coordinator = headers[RoleCode.COORDINATOR]
    feature = (await _create(client, coordinator, incident["id"], label="A")).json()

    response = await client.patch(
        f"{API}/map-features/{feature['id']}",
        json={"version": 1, "geometry": _polygon(SQUARE), "label": "A"},
        headers=coordinator,
    )

    assert response.status_code == 200
    assert response.json()["properties"]["version"] == 1
    assert len(await _events(client, coordinator, incident["id"])) == 1


# --- Concurrencia ----------------------------------------------------------------------


async def test_stale_version_is_rejected_without_overwriting(
    client: AsyncClient, headers: dict[RoleCode, Headers], incident: dict[str, Any]
) -> None:
    coordinator = headers[RoleCode.COORDINATOR]
    feature = (await _create(client, coordinator, incident["id"])).json()
    path = f"{API}/map-features/{feature['id']}"
    first = await client.patch(
        path, json={"version": 1, "geometry": _polygon(MOVED)}, headers=coordinator
    )
    assert first.status_code == 200

    # Quien seguía con la versión 1 no sobrescribe el cambio ajeno.
    stale_edit = await client.patch(path, json={"version": 1, "label": "x"}, headers=coordinator)
    stale_retire = await client.post(
        f"{path}/retire", json={"version": 1, "reason": "x"}, headers=coordinator
    )

    for response in (stale_edit, stale_retire):
        assert response.status_code == 409
        assert response.json() == {"detail": "version_conflict"}
    (current,) = await _features(client, coordinator, incident["id"])
    assert current["geometry"] == _polygon(MOVED)
    assert (current["properties"]["version"], current["properties"]["label"]) == (2, None)
    assert len(await _events(client, coordinator, incident["id"])) == 2


# --- Permisos --------------------------------------------------------------------------


async def test_operator_reads_but_cannot_draw(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    incident: dict[str, Any],
) -> None:
    feature = (await _create(client, headers[RoleCode.COORDINATOR], incident["id"])).json()
    operator = headers[RoleCode.OPERATOR]
    before = await _counts(session)

    assert len(await _features(client, operator, incident["id"])) == 1
    attempts = [
        await _create(client, operator, incident["id"]),
        await client.patch(
            f"{API}/map-features/{feature['id']}",
            json={"version": 1, "geometry": _polygon(MOVED)},
            headers=operator,
        ),
        await client.post(
            f"{API}/map-features/{feature['id']}/retire",
            json={"version": 1, "reason": "x"},
            headers=operator,
        ),
    ]

    for response in attempts:
        assert response.status_code == 403
        assert response.json() == {"detail": "permission_denied"}
    assert await _counts(session) == before
    (current,) = await _features(client, operator, incident["id"])
    assert current == feature


async def test_requires_authentication(client: AsyncClient, incident: dict[str, Any]) -> None:
    response = await client.get(f"{API}/incidents/{incident['id']}/map-features")
    assert response.status_code == 401


# --- Incidentes cerrados y elementos retirados -----------------------------------------


async def test_closed_incident_is_read_only(
    client: AsyncClient, headers: dict[RoleCode, Headers], incident: dict[str, Any]
) -> None:
    coordinator = headers[RoleCode.COORDINATOR]
    feature = (await _create(client, coordinator, incident["id"])).json()
    closed = await client.post(
        f"{API}/incidents/{incident['id']}/status",
        json={"status": "cancelled", "version": incident["version"]},
        headers=coordinator,
    )
    assert closed.status_code == 200, closed.text

    attempts = [
        await _create(client, coordinator, incident["id"]),
        await client.patch(
            f"{API}/map-features/{feature['id']}",
            json={"version": 1, "label": "x"},
            headers=coordinator,
        ),
        await client.post(
            f"{API}/map-features/{feature['id']}/retire",
            json={"version": 1, "reason": "x"},
            headers=coordinator,
        ),
    ]

    for response in attempts:
        assert response.status_code == 422
        assert response.json() == {"detail": "incident_closed"}
    # Se sigue consultando, igual que el resto del incidente cerrado.
    (current,) = await _features(client, coordinator, incident["id"])
    assert current == feature


async def test_retired_feature_cannot_be_changed(
    client: AsyncClient, headers: dict[RoleCode, Headers], incident: dict[str, Any]
) -> None:
    coordinator = headers[RoleCode.COORDINATOR]
    feature = (await _create(client, coordinator, incident["id"])).json()
    path = f"{API}/map-features/{feature['id']}"
    await client.post(f"{path}/retire", json={"version": 1, "reason": "x"}, headers=coordinator)

    edit = await client.patch(path, json={"version": 2, "label": "x"}, headers=coordinator)
    again = await client.post(
        f"{path}/retire", json={"version": 2, "reason": "x"}, headers=coordinator
    )

    for response in (edit, again):
        assert response.status_code == 422
        assert response.json() == {"detail": "map_feature_retired"}


async def test_unknown_incident_or_feature(
    client: AsyncClient, headers: dict[RoleCode, Headers]
) -> None:
    coordinator = headers[RoleCode.COORDINATOR]
    missing = str(uuid.uuid4())

    assert (await _create(client, coordinator, missing)).json() == {"detail": "incident_not_found"}
    listed = await client.get(f"{API}/incidents/{missing}/map-features", headers=coordinator)
    assert (listed.status_code, listed.json()) == (404, {"detail": "incident_not_found"})
    edit = await client.patch(
        f"{API}/map-features/{missing}", json={"version": 1, "label": "x"}, headers=coordinator
    )
    assert (edit.status_code, edit.json()) == (404, {"detail": "map_feature_not_found"})


# --- Geometrías inválidas ---------------------------------------------------------------


def _circle(vertices: int) -> list[list[float]]:
    ring = [
        [
            round(-5.85 + 0.01 * math.cos(2 * math.pi * i / vertices), 6),
            round(43.36 + 0.01 * math.sin(2 * math.pi * i / vertices), 6),
        ]
        for i in range(vertices)
    ]
    return [*ring, ring[0]]


BOWTIE = [[-5.86, 43.36], [-5.85, 43.37], [-5.85, 43.36], [-5.86, 43.37], [-5.86, 43.36]]


@pytest.mark.parametrize(
    ("body", "code"),
    [
        pytest.param(
            {"kind": "road_closure"}, "map_feature_kind_not_enabled", id="tipo-no-habilitado"
        ),
        pytest.param(
            {"geometry": {"type": "LineString", "coordinates": SQUARE}},
            "geometry_kind_mismatch",
            id="tipo-de-geometria",
        ),
        pytest.param({"geometry": _polygon([])}, "geometry_empty", id="vacia"),
        pytest.param(
            {"geometry": {"type": "Polygon", "coordinates": []}}, "geometry_empty", id="sin-anillos"
        ),
        pytest.param(
            {"geometry": {"type": "Polygon", "coordinates": [SQUARE, SQUARE]}},
            "polygon_holes_not_supported",
            id="huecos",
        ),
        pytest.param({"geometry": _polygon(SQUARE[:-1])}, "ring_not_closed", id="anillo-abierto"),
        pytest.param(
            {
                "geometry": _polygon(
                    [[-5.86, 43.36], [-5.85, 43.36], [-5.84, 43.36], [-5.86, 43.36]]
                )
            },
            "degenerate_polygon",
            id="degenerado",
        ),
        pytest.param(
            {"geometry": _polygon([[0.0, 0.0], [0.1, 0.0], [0.1, 0.1], [0.0, 0.0]])},
            "location_out_of_area",
            id="fuera-del-area",
        ),
        pytest.param(
            {"geometry": _polygon(BOWTIE)}, "geometry_invalid_topology", id="autointerseccion"
        ),
        pytest.param(
            {"geometry": _polygon(_circle(MAX_POLYGON_VERTICES + 1))},
            "too_many_vertices",
            id="exceso-de-vertices",
        ),
    ],
)
async def test_invalid_geometry_is_rejected_safely(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    incident: dict[str, Any],
    body: dict[str, Any],
    code: str,
) -> None:
    before = await _counts(session)

    response = await _create(client, headers[RoleCode.COORDINATOR], incident["id"], **body)

    assert response.status_code == 422
    assert response.json() == {"detail": code}
    assert await _counts(session) == before


async def test_edit_with_invalid_geometry_changes_nothing(
    client: AsyncClient, headers: dict[RoleCode, Headers], incident: dict[str, Any]
) -> None:
    coordinator = headers[RoleCode.COORDINATOR]
    feature = (await _create(client, coordinator, incident["id"])).json()
    path = f"{API}/map-features/{feature['id']}"

    bowtie = await client.patch(
        path, json={"version": 1, "geometry": _polygon(BOWTIE)}, headers=coordinator
    )
    null = await client.patch(path, json={"version": 1, "geometry": None}, headers=coordinator)

    assert bowtie.json() == {"detail": "geometry_invalid_topology"}
    assert null.json() == {"detail": "field_not_nullable"}
    (current,) = await _features(client, coordinator, incident["id"])
    assert current == feature
    assert len(await _events(client, coordinator, incident["id"])) == 1


@pytest.mark.parametrize(
    "raw",
    [
        # Más posiciones que el tope del esquema.
        pytest.param(
            '{"kind":"perimeter","geometry":{"type":"Polygon","coordinates":[['
            + ",".join(["[-5.861357,43.362468]"] * (MAX_RING_POSITIONS_INPUT + 1))
            + "]]}}",
            id="desproporcionada",
        ),
        # NaN (JSON no estándar) y un valor fuera de rango.
        pytest.param(
            '{"kind":"perimeter","geometry":{"type":"Polygon","coordinates":'
            "[[[-5.861357,43.362468],[NaN,43.362468],[-5.851357,43.372468],[-5.861357,43.362468]]]}}",
            id="nan",
        ),
        pytest.param(
            '{"kind":"perimeter","geometry":{"type":"Polygon","coordinates":'
            "[[[-5.861357,43.362468],[-5.851357,95.362468],[-5.851357,43.372468],[-5.861357,43.362468]]]}}",
            id="fuera-de-rango",
        ),
    ],
)
async def test_schema_errors_never_echo_the_geometry(
    client: AsyncClient,
    session: AsyncSession,
    headers: dict[RoleCode, Headers],
    incident: dict[str, Any],
    raw: str,
) -> None:
    before = await _counts(session)

    response = await client.post(
        f"{API}/incidents/{incident['id']}/map-features",
        content=raw,
        headers={**headers[RoleCode.COORDINATOR], "Content-Type": "application/json"},
    )

    assert response.status_code == 422
    for value in ("5.861357", "43.362468", "95.362468"):
        assert value not in response.text
    assert await _counts(session) == before


async def test_geometries_never_reach_the_logs(
    client: AsyncClient,
    headers: dict[RoleCode, Headers],
    incident: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    coordinator = headers[RoleCode.COORDINATOR]

    feature = (
        await client.post(
            f"{API}/incidents/{incident['id']}/map-features",
            json={"kind": "perimeter", "geometry": _polygon(LEAK)},
            headers=coordinator,
        )
    ).json()
    await client.patch(
        f"{API}/map-features/{feature['id']}",
        json={"version": 1, "geometry": _polygon([[x + 0.001, y] for x, y in LEAK])},
        headers=coordinator,
    )
    await _create(
        client,
        coordinator,
        incident["id"],
        geometry=_polygon([LEAK[0], LEAK[2], LEAK[1], LEAK[3], LEAK[0]]),
    )
    await _features(client, coordinator, incident["id"])

    for value in ("5.861357", "43.362468", "5.851357", "43.372468", "5.860357"):
        assert value not in caplog.text
