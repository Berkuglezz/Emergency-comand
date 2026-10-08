import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Sequence,
    String,
    Text,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.domain.enums import IncidentPriority, IncidentStatus
from app.models.incident_type import IncidentType
from app.models.location import Location

# Secuencia única para los códigos legibles (`INC-000123`) de todos los
# incidentes, simulados o reales. `is_simulated` distingue el origen.
INCIDENT_CODE_SEQUENCE = Sequence("incident_code_seq", metadata=Base.metadata)


class Incident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Incidente: entidad central (CLAUDE.md §5).

    - Ubicación en `Location` (1:1): municipio, descripción y, opcionalmente,
      coordenadas. Cambiarla solo modifica `locations`; el servicio fuerza el
      incremento de `version` del incidente.
    - `version` implementa el bloqueo optimista: cada UPDATE la incrementa y
      falla si otro cambio llegó antes.
    """

    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint(
            "affected_people IS NULL OR affected_people >= 0", name="affected_people_non_negative"
        ),
        CheckConstraint(
            "parent_incident_id IS NULL OR parent_incident_id <> id", name="not_own_parent"
        ),
        # Listado de incidentes activos (el caso más frecuente).
        Index(
            "ix_incidents_active_reported_at",
            "reported_at",
            postgresql_where=text("status NOT IN ('closed', 'cancelled')"),
        ),
    )

    code: Mapped[str] = mapped_column(String(20), unique=True)
    type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incident_types.id", ondelete="RESTRICT"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[IncidentStatus] = mapped_column(
        str_enum(IncidentStatus, "incident_status"), index=True
    )
    priority: Mapped[IncidentPriority] = mapped_column(
        str_enum(IncidentPriority, "incident_priority"), index=True
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), unique=True
    )
    affected_people: Mapped[int | None]
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    # Un único nivel de jerarquía (padre → hijo); lo comprueba el servicio.
    parent_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id", ondelete="RESTRICT"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    is_simulated: Mapped[bool] = mapped_column(server_default=false())
    version: Mapped[int] = mapped_column(server_default=text("1"))
    reported_at: Mapped[datetime] = mapped_column(server_default=func.now(), index=True)
    closed_at: Mapped[datetime | None]

    type: Mapped[IncidentType] = relationship(lazy="raise")
    location: Mapped[Location] = relationship(lazy="raise")
    parent: Mapped["Incident | None"] = relationship(remote_side="Incident.id", lazy="raise")

    # eager_defaults: los valores calculados por la BD (updated_at, version…) se
    # leen en el mismo INSERT/UPDATE (RETURNING); en async no hay carga perezosa.
    __mapper_args__ = {"version_id_col": version, "eager_defaults": True}  # noqa: RUF012
