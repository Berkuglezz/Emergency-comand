import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, false, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin, str_enum
from app.domain.enums import IncidentEventType


class IncidentEvent(UUIDPrimaryKeyMixin, Base):
    """Historial funcional del incidente (timeline). Solo inserción.

    - Se escribe en la misma transacción que el cambio que describe.
    - PostgreSQL impide modificarlo o borrarlo (trigger en la migración).
    - `payload` contiene códigos y valores, nunca textos ni datos personales
      sensibles; el frontend compone el texto traducido.
    - No es el sistema de auditoría de seguridad, que es un concepto aparte.
    """

    __tablename__ = "incident_events"
    __table_args__ = (
        Index("ix_incident_events_incident_id_occurred_at", "incident_id", "occurred_at"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="RESTRICT"))
    event_type: Mapped[IncidentEventType] = mapped_column(
        str_enum(IncidentEventType, "incident_event_type", length=40)
    )
    occurred_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Usuario que provocó el cambio; nulo si lo generó el sistema (p. ej. el seed).
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    is_simulated: Mapped[bool] = mapped_column(server_default=false())

    # `occurred_at` lo fija la BD y se lee en el mismo INSERT (RETURNING).
    __mapper_args__ = {"eager_defaults": True}  # noqa: RUF012
