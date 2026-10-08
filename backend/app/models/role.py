from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin, str_enum
from app.domain.enums import RoleCode


class Role(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    """Rol de usuario. Los permisos de cada rol se definen en código
    (`app.core.permissions`), no en base de datos."""

    __tablename__ = "roles"

    code: Mapped[RoleCode] = mapped_column(str_enum(RoleCode, "role_code"), unique=True)
