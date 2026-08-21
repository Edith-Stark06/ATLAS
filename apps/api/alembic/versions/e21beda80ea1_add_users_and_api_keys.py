"""add users and api keys

Two tables share the `user_role` enum. Autogenerate emits an inline
`sa.Enum` on each, which makes Postgres create the type twice (the second
fails) and never drops it on downgrade — so a downgrade/upgrade round-trip
dies with "type user_role already exists". The type is therefore created and
dropped explicitly here, and referenced with `create_type=False`.

Revision ID: e21beda80ea1
Revises: 5ad63a0cd8cd
Create Date: 2026-08-22 03:52:10.517426
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e21beda80ea1"
down_revision: str | None = "5ad63a0cd8cd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_VALUES = ("viewer", "operator", "admin")

# create_type=False: the CREATE TYPE is issued once, by hand, below.
role_enum = postgresql.ENUM(*ROLE_VALUES, name="user_role", create_type=False)


def upgrade() -> None:
    role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("prefix", sa.String(length=32), nullable=False),
        sa.Column("role", role_enum, nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_keys_agent_id"), "api_keys", ["agent_id"], unique=False)
    op.create_index(op.f("ix_api_keys_prefix"), "api_keys", ["prefix"], unique=False)
    op.create_index(op.f("ix_api_keys_token_hash"), "api_keys", ["token_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_api_keys_token_hash"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_prefix"), table_name="api_keys")
    op.drop_index(op.f("ix_api_keys_agent_id"), table_name="api_keys")
    op.drop_table("api_keys")

    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    # Must come after both tables: Postgres refuses to drop a type still in use.
    role_enum.drop(op.get_bind(), checkfirst=True)
