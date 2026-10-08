from typing import Any

import pytest

from app.domain.exceptions import InvalidInputError
from app.domain.incident_details import validate_details


def test_types_without_schema_require_empty_details() -> None:
    assert validate_details(None, {}) == {}
    with pytest.raises(InvalidInputError) as exc:
        validate_details(None, {"anything": 1})
    assert exc.value.code == "details_not_allowed"


def test_wildfire_details_are_validated_and_normalized() -> None:
    assert validate_details("wildfire", {"affected_hectares": "12.5", "vegetation": "forest"}) == {
        "affected_hectares": "12.5",
        "vegetation": "forest",
    }
    # Todos los campos son opcionales.
    assert validate_details("wildfire", {}) == {}


def test_flood_details_are_validated() -> None:
    assert validate_details("flood", {"water_level_cm": 40}) == {"water_level_cm": 40}


@pytest.mark.parametrize(
    ("key", "data"),
    [
        ("wildfire", {"affected_hectares": -1}),
        ("wildfire", {"vegetation": "desert"}),
        ("wildfire", {"unexpected": "field"}),
        ("flood", {"water_level_cm": -5}),
        ("flood", {"water_level_cm": "mucho"}),
    ],
)
def test_invalid_details_are_rejected(key: str, data: dict[str, Any]) -> None:
    with pytest.raises(InvalidInputError) as exc:
        validate_details(key, data)
    assert exc.value.code == "invalid_details"


def test_unknown_schema_key_is_a_configuration_error() -> None:
    with pytest.raises(LookupError):
        validate_details("no-existe", {})
