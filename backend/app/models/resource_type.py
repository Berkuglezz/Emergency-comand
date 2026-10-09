from sqlalchemy import CheckConstraint, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, str_enum
from app.domain.enums import ResourceCategory


class ResourceType(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Catálogo de tipos de recurso (datos de referencia, no demo)."""

    __tablename__ = "resource_types"
    __table_args__ = (CheckConstraint("average_speed_kmh > 0", name="average_speed_positive"),)

    code: Mapped[str] = mapped_column(String(64), unique=True)
    category: Mapped[ResourceCategory] = mapped_column(
        str_enum(ResourceCategory, "resource_category")
    )
    # Nombre de un icono de Lucide.
    icon: Mapped[str] = mapped_column(String(64))
    # Velocidad media para la ETA estimada (CLAUDE.md §2.8). Dato de catálogo.
    average_speed_kmh: Mapped[int]
    is_active: Mapped[bool] = mapped_column(server_default=true())
