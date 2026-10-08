from sqlalchemy import String, text, true
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, str_enum
from app.domain.enums import IncidentCategory, IncidentPriority


class IncidentType(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Catálogo de tipos de incidente (datos de referencia, no demo).

    Sin nombres ni textos: el frontend traduce `code`, la categoría y los
    riesgos a partir de sus códigos.
    """

    __tablename__ = "incident_types"

    code: Mapped[str] = mapped_column(String(64), unique=True)
    category: Mapped[IncidentCategory] = mapped_column(
        str_enum(IncidentCategory, "incident_category")
    )
    # Nombre de un icono de Lucide.
    icon: Mapped[str] = mapped_column(String(64))
    default_priority: Mapped[IncidentPriority] = mapped_column(
        str_enum(IncidentPriority, "incident_priority")
    )
    # Códigos de `resource_types`.
    suggested_resource_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)), server_default=text("'{}'")
    )
    # Códigos de riesgo (traducidos en el frontend).
    common_risks: Mapped[list[str]] = mapped_column(ARRAY(String(64)), server_default=text("'{}'"))
    # Clave del esquema de `details` (`domain/incident_details.py`); sin clave, `details = {}`.
    details_schema_key: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(server_default=true())
