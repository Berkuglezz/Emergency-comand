"""Reglas puras del mapa operativo (CLAUDE.md §2.12, M.1)."""

import math
from typing import Any

import pytest

from app.domain.enums import MapFeatureKind
from app.domain.exceptions import InvalidInputError
from app.domain.map_features import (
    API_ENABLED_KINDS,
    GEOMETRY_TYPE_BY_KIND,
    MAX_EVENT_PAYLOAD_BYTES,
    MAX_POLYGON_VERTICES,
    ensure_event_payload_size,
    ensure_kind_enabled,
    validate_polygon,
)

K = MapFeatureKind
# Cuadrado de ~1 km en Oviedo, en orden GeoJSON [lon, lat], cerrado.
SQUARE = [[-5.86, 43.36], [-5.85, 43.36], [-5.85, 43.37], [-5.86, 43.37], [-5.86, 43.36]]


def _polygon(ring: list[list[float]], kind: K = K.PERIMETER) -> Any:
    return validate_polygon(kind, "Polygon", [ring])


def _code(callable_: Any) -> str:
    with pytest.raises(InvalidInputError) as raised:
        callable_()
    return raised.value.code


def test_every_kind_has_a_geometry_type_and_only_perimeter_is_enabled() -> None:
    assert set(GEOMETRY_TYPE_BY_KIND) == set(MapFeatureKind)
    assert {K.PERIMETER} == API_ENABLED_KINDS
    ensure_kind_enabled(K.PERIMETER)
    for kind in set(MapFeatureKind) - {K.PERIMETER}:
        assert _code(lambda kind=kind: ensure_kind_enabled(kind)) == "map_feature_kind_not_enabled"


def test_valid_polygon_is_normalized() -> None:
    polygon = _polygon([[-5.8600001, 43.36], *SQUARE[1:4], [-5.8600001, 43.36]])
    assert polygon.vertex_count == 4
    assert polygon.ring[0] == polygon.ring[-1] == (-5.86, 43.36)  # 6 decimales
    assert polygon.as_geojson() == {"type": "Polygon", "coordinates": [SQUARE]}
    assert polygon.as_wkt().startswith("POLYGON((-5.86 43.36, ")


def test_consecutive_duplicates_are_collapsed() -> None:
    ring = [SQUARE[0], SQUARE[0], SQUARE[1], SQUARE[2], SQUARE[2], SQUARE[3], SQUARE[0]]
    assert _polygon(ring).vertex_count == 4


@pytest.mark.parametrize(
    ("geometry_type", "coordinates", "code"),
    [
        ("LineString", [SQUARE], "geometry_kind_mismatch"),
        ("Point", [SQUARE], "geometry_kind_mismatch"),
        ("Polygon", [], "geometry_empty"),
        ("Polygon", [[]], "geometry_empty"),
        ("Polygon", [SQUARE, SQUARE], "polygon_holes_not_supported"),
    ],
)
def test_structure_errors(geometry_type: str, coordinates: Any, code: str) -> None:
    assert _code(lambda: validate_polygon(K.PERIMETER, geometry_type, coordinates)) == code


@pytest.mark.parametrize(
    ("ring", "code"),
    [
        (SQUARE[:-1], "ring_not_closed"),
        ([[-5.86, 43.36], [-5.85, 43.36], [-5.86, 43.36]], "degenerate_polygon"),
        # Colineales: tres vértices distintos, área cero.
        ([[-5.86, 43.36], [-5.85, 43.36], [-5.84, 43.36], [-5.86, 43.36]], "degenerate_polygon"),
        # Todos iguales tras redondear a 6 decimales.
        (
            [[-5.86, 43.36], [-5.8600001, 43.36], [-5.86, 43.3600002], [-5.86, 43.36]],
            "degenerate_polygon",
        ),
        ([[0.0, 0.0], [0.1, 0.0], [0.1, 0.1], [0.0, 0.0]], "location_out_of_area"),
        (
            [[-5.86, 43.36], [-5.85, 43.36], [math.nan, 43.37], [-5.86, 43.36]],
            "invalid_coordinates",
        ),
        (
            [[-5.86, 43.36], [-5.85, 43.36], [math.inf, 43.37], [-5.86, 43.36]],
            "invalid_coordinates",
        ),
        ([[-5.86, 43.36], [-5.85, 95.0], [-5.85, 43.37], [-5.86, 43.36]], "invalid_coordinates"),
        (
            [[-5.86, 43.36, 10.0], [-5.85, 43.36], [-5.85, 43.37], [-5.86, 43.36]],
            "invalid_coordinates",
        ),
    ],
)
def test_shape_errors(ring: list[list[float]], code: str) -> None:
    assert _code(lambda: _polygon(ring)) == code


def _circle(vertices: int) -> list[list[float]]:
    ring = [
        [
            -5.85 + 0.01 * math.cos(2 * math.pi * i / vertices),
            43.36 + 0.01 * math.sin(2 * math.pi * i / vertices),
        ]
        for i in range(vertices)
    ]
    return [*ring, ring[0]]


def test_vertex_limit() -> None:
    assert _polygon(_circle(MAX_POLYGON_VERTICES)).vertex_count == MAX_POLYGON_VERTICES
    assert _code(lambda: _polygon(_circle(MAX_POLYGON_VERTICES + 1))) == "too_many_vertices"


def test_errors_never_carry_coordinates() -> None:
    with pytest.raises(InvalidInputError) as raised:
        _polygon([[-5.123456, 43.654321], [-5.1, 43.6], [-5.123456, 43.654321]])
    assert "5.12" not in str(raised.value)
    assert "43.65" not in repr(raised.value)


def test_event_payload_limit() -> None:
    ensure_event_payload_size({"before": None, "after": {"type": "Polygon"}})
    oversized = {"note": "x" * (MAX_EVENT_PAYLOAD_BYTES + 1)}
    assert _code(lambda: ensure_event_payload_size(oversized)) == "geometry_too_large"


def test_symmetric_bowtie_is_left_to_postgis() -> None:
    """Área con signo cero, pero no es degenerado: es una autointersección, y
    eso lo decide PostGIS (`geometry_invalid_topology`)."""
    bowtie = [[-5.86, 43.36], [-5.85, 43.37], [-5.85, 43.36], [-5.86, 43.37], [-5.86, 43.36]]
    assert _polygon(bowtie).vertex_count == 4
