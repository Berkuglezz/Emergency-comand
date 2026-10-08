from sqlalchemy import String, false, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Organización a la que pertenecen los usuarios (servicio, agencia…)."""

    __tablename__ = "organizations"

    code: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(server_default=true())
    # Marca las organizaciones ficticias de la demo para que nunca se
    # confundan con un servicio real (CLAUDE.md §8).
    is_simulated: Mapped[bool] = mapped_column(server_default=false())
