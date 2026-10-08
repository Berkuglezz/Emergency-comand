"""Esquema inicial: roles, organizations, users y refresh_tokens.

Habilita PostGIS para no cambiar de imagen ni de base de datos más adelante,
pero no crea ninguna columna, índice ni consulta geográfica (Fase 1).

Revision ID: 2c90a9ee7694
Revises:
Create Date: 2026-10-07 12:46:26.212222

"""

import uuid
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2c90a9ee7694"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Los roles son datos de referencia del sistema (sus permisos viven en código),
# no datos de demostración: se crean aquí y existen en todos los entornos.
ROLE_CODES = ("admin", "coordinator", "operator")


def _id_column() -> sa.Column[uuid.UUID]:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def _timestamp_column(name: str) -> sa.Column[datetime]:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    roles = op.create_table(
        "roles",
        _id_column(),
        sa.Column("code", sa.String(length=32), nullable=False),
        _timestamp_column("created_at"),
        sa.CheckConstraint(
            "code IN ('admin', 'coordinator', 'operator')", name=op.f("ck_roles_role_code")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roles")),
        sa.UniqueConstraint("code", name=op.f("uq_roles_code")),
    )
    op.create_table(
        "organizations",
        _id_column(),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_simulated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("code", name=op.f("uq_organizations_code")),
    )
    op.create_table(
        "users",
        _id_column(),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        _timestamp_column("created_at"),
        _timestamp_column("updated_at"),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_users_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["role_id"], ["roles.id"], name=op.f("fk_users_role_id_roles"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_organization_id"), "users", ["organization_id"])
    op.create_index(op.f("ix_users_role_id"), "users", ["role_id"])
    op.create_table(
        "refresh_tokens",
        _id_column(),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        _timestamp_column("created_at"),
        sa.ForeignKeyConstraint(
            ["replaced_by_id"],
            ["refresh_tokens.id"],
            name=op.f("fk_refresh_tokens_replaced_by_id_refresh_tokens"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    op.create_index(op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"])
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"])

    op.bulk_insert(roles, [{"code": code} for code in ROLE_CODES])


def downgrade() -> None:
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index(op.f("ix_users_role_id"), table_name="users")
    op.drop_index(op.f("ix_users_organization_id"), table_name="users")
    op.drop_table("users")
    op.drop_table("organizations")
    op.drop_table("roles")
    # La extensión PostGIS no se elimina: puede haberla creado la imagen de la
    # base de datos y otras bases o esquemas podrían depender de ella.
