"""Base declarativa y columnas comunes de los modelos SQLAlchemy."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, MetaData, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Nombres de restricciones deterministas: Alembic genera migraciones estables
# y las restricciones se pueden referenciar por nombre.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(AsyncAttrs, DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Toda fecha se guarda como `timestamptz` (UTC). Nunca fechas sin zona.
    # SQLAlchemy lee este atributo como configuración de clase; no se muta.
    type_annotation_map = {datetime: DateTime(timezone=True)}  # noqa: RUF012


def str_enum[E: StrEnum](enum_cls: type[E], name: str, length: int = 32) -> Enum:
    """Columna de enum como VARCHAR + CHECK (no ENUM nativo de PostgreSQL):
    añadir un valor no exige `ALTER TYPE`. Guarda el valor (`code.value`)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=lambda members: [member.value for member in members],
    )


class UUIDPrimaryKeyMixin:
    # Se genera en Python para conocer el id antes del flush; el valor por
    # defecto del servidor cubre las inserciones en SQL (p. ej. migraciones).
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
    )
