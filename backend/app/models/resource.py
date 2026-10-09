import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, false, func, text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum
from app.domain.enums import ResourceStatus
from app.models.location import Location
from app.models.organization import Organization
from app.models.resource_type import ResourceType


class Resource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Recurso operativo de una organización.

    - Base (dónde está destinado) en `Location` 1:1 (`base_location_id`): es
      el origen de la ETA estimada. La posición actual/GPS es de la Fase 5.
    - Sin historial propio: `status_changed_at` registra el último cambio de
      estado; las asignaciones (`ResourceAssignment`) guardan su historial.
    - No se borra: se desactiva con `is_active`.
    """

    __tablename__ = "resources"

    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resource_types.id", ondelete="RESTRICT"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[ResourceStatus] = mapped_column(
        str_enum(ResourceStatus, "resource_status"), index=True
    )
    status_changed_at: Mapped[datetime] = mapped_column(server_default=func.now())
    base_location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), unique=True
    )
    is_active: Mapped[bool] = mapped_column(server_default=true())
    is_simulated: Mapped[bool] = mapped_column(server_default=false())
    version: Mapped[int] = mapped_column(server_default=text("1"))

    type: Mapped[ResourceType] = relationship(lazy="raise")
    organization: Mapped[Organization] = relationship(lazy="raise")
    base: Mapped[Location] = relationship(lazy="raise")

    # eager_defaults: los valores calculados por la BD (updated_at, version…) se
    # leen en el mismo INSERT/UPDATE (RETURNING); en async no hay carga perezosa.
    __mapper_args__ = {"version_id_col": version, "eager_defaults": True}  # noqa: RUF012
