"""Reglas geográficas puras (`app.domain.geo`)."""

import pytest

from app.domain.exceptions import InvalidInputError
from app.domain.geo import (
    DEMO_AREA,
    BoundingBox,
    parse_bbox,
    round_coordinate,
    validate_coordinates,
)


def test_coordinates_are_rounded_to_six_decimals() -> None:
    assert round_coordinate(43.36141249) == 43.361412
    assert round_coordinate(-5.84938871) == -5.849389


def test_no_coordinates_is_valid() -> None:
    assert validate_coordinates(None, None) is None


def test_coordinates_inside_the_demo_area() -> None:
    assert validate_coordinates(43.3614, -5.8494) == (43.3614, -5.8494)


@pytest.mark.parametrize(("latitude", "longitude"), [(43.36, None), (None, -5.85)])
def test_coordinates_come_in_pairs(latitude: float | None, longitude: float | None) -> None:
    with pytest.raises(InvalidInputError) as error:
        validate_coordinates(latitude, longitude)
    assert error.value.code == "coordinates_incomplete"


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (-5.8494, 43.3614),  # latitud y longitud intercambiadas
        (40.4168, -3.7038),  # fuera de Asturias
        (0.0, 0.0),
    ],
)
def test_coordinates_outside_the_demo_area(latitude: float, longitude: float) -> None:
    with pytest.raises(InvalidInputError) as error:
        validate_coordinates(latitude, longitude)
    assert error.value.code == "location_out_of_area"
    # El mensaje de la excepción no contiene las coordenadas.
    assert str(latitude) not in str(error.value)


def test_demo_area_covers_the_main_zones() -> None:
    for latitude, longitude in [(43.3614, -5.8494), (43.5357, -5.6615), (43.5547, -5.9248)]:
        assert DEMO_AREA.contains(latitude, longitude)


def test_parse_bbox_uses_geojson_order() -> None:
    assert parse_bbox(" -5.9, 43.3,-5.8 ,43.4") == BoundingBox(-5.9, 43.3, -5.8, 43.4)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "1,2,3",
        "1,2,3,4,5",
        "x,43,-5,44",
        "-5,43,-6,44",
        "-6,44,-5,44",
        "-181,0,0,1",
        "nan,0,1,1",
    ],
)
def test_parse_bbox_rejects_invalid_values(value: str) -> None:
    with pytest.raises(InvalidInputError) as error:
        parse_bbox(value)
    assert error.value.code == "invalid_bbox"
