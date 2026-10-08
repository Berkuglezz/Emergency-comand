import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.organization import Organization
from app.models.role import Role


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # El email se normaliza a minúsculas antes de guardarse; la restricción
        # garantiza que la unicidad no dependa de mayúsculas.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    email: Mapped[str] = mapped_column(String(254), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    # Hash Argon2 (formato PHC). Nunca se registra ni se devuelve.
    password_hash: Mapped[str] = mapped_column(String(255))
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), index=True
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(server_default=true())
    last_login_at: Mapped[datetime | None]

    # lazy="raise": en async no hay carga perezosa implícita; los repositorios
    # cargan las relaciones de forma explícita (selectinload/joinedload).
    role: Mapped[Role] = relationship(lazy="raise")
    organization: Mapped[Organization | None] = relationship(lazy="raise")
