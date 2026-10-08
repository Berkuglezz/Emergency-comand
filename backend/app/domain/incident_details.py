"""Datos específicos por tipo de incidente (campo `details`, CLAUDE.md §5).

- Cada `details_schema_key` de `incident_types` tiene un modelo pydantic aquí.
- Un tipo sin clave exige `details = {}`.
- `details` nunca contiene datos que se filtren, ordenen o agreguen con
  frecuencia, ni datos personales sensibles.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.exceptions import InvalidInputError


class _Details(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VegetationType(StrEnum):
    FOREST = "forest"
    SCRUB = "scrub"
    AGRICULTURAL = "agricultural"


class WildfireDetails(_Details):
    affected_hectares: Decimal | None = Field(default=None, ge=0, le=100_000, decimal_places=2)
    vegetation: VegetationType | None = None


class FloodDetails(_Details):
    water_level_cm: int | None = Field(default=None, ge=0, le=2_000)


DETAILS_SCHEMAS: dict[str, type[_Details]] = {
    "wildfire": WildfireDetails,
    "flood": FloodDetails,
}


def validate_details(schema_key: str | None, data: dict[str, Any]) -> dict[str, Any]:
    """Valida `details` para un tipo y devuelve la forma normalizada (JSON)."""
    if schema_key is None:
        if data:
            raise InvalidInputError("details_not_allowed")
        return {}
    schema = DETAILS_SCHEMAS.get(schema_key)
    if schema is None:
        # Error de configuración del catálogo, no del usuario.
        raise LookupError(f"details_schema_key sin esquema registrado: {schema_key}")
    try:
        return schema.model_validate(data).model_dump(mode="json", exclude_none=True)
    except ValidationError as exc:
        raise InvalidInputError("invalid_details") from exc
