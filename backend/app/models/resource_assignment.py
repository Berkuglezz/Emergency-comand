import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, false, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.domain.enums import ReleaseReason
from app.domain.eta import EtaOrigin
from app.models.incident import Incident
from app.models.resource import Resource


class ResourceAssignment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Asignación de un recurso a un incidente (CLAUDE.md §2.8).

    - Activa mientras `released_at` es nulo. Nunca se borra: las filas son el
      historial de asignaciones del recurso.
    - Un recurso solo puede tener una asignación activa (índice único parcial);
      un incidente puede tener varias.
    - `eta_*` es la estimación **en el momento de asignar**: cambiar después la
      base o la velocidad del tipo no altera lo registrado.
    """

    __tablename__ = "resource_assignments"
    __table_args__ = (
        Index(
            "uq_resource_assignments_active_resource",
            "resource_id",
            unique=True,
            postgresql_where=text("released_at IS NULL"),
        ),
        Index("ix_resource_assignments_incident_released", "incident_id", "released_at"),
        Index("ix_resource_assignments_resource_assigned", "resource_id", "assigned_at"),
    )

    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="RESTRICT"))
    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resources.id", ondelete="RESTRICT"))
    assigned_at: Mapped[datetime]
    assigned_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    arrived_at: Mapped[datetime | None]
    released_at: Mapped[datetime | None]
    released_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    release_reason: Mapped[ReleaseReason | None] = mapped_column(
        str_enum(ReleaseReason, "release_reason")
    )
    eta_minutes: Mapped[int | None]
    eta_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    eta_origin: Mapped[EtaOrigin | None] = mapped_column(str_enum(EtaOrigin, "eta_origin"))
    is_simulated: Mapped[bool] = mapped_column(server_default=false())

    incident: Mapped[Incident] = relationship(lazy="raise")
    resource: Mapped[Resource] = relationship(lazy="raise")

    @property
    def is_active(self) -> bool:
        return self.released_at is None
