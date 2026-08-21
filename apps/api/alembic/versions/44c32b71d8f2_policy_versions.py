"""policy versions

Revision ID: 44c32b71d8f2
Revises: 644db26045e9
Create Date: 2026-08-21 14:50:27.350799
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "44c32b71d8f2"
down_revision: str | None = "644db26045e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


#: policies and policy_versions reference each other, so the FK from
#: policies must be named explicitly — autogenerate emits `None` for it,
#: which works on the way up but makes drop_constraint fail on the way down.
ACTIVE_VERSION_FK = "fk_policies_active_version_id_policy_versions"


def upgrade() -> None:
    op.create_table(
        "policy_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("policy_id", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("rule", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_policy_versions_created_at"), "policy_versions", ["created_at"], unique=False
    )
    op.create_index(
        op.f("ix_policy_versions_policy_id"), "policy_versions", ["policy_id"], unique=False
    )
    op.add_column("policies", sa.Column("active_version_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        ACTIVE_VERSION_FK,
        "policies",
        "policy_versions",
        ["active_version_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop the policies -> policy_versions FK before the table it points at,
    # otherwise Postgres refuses to drop policy_versions.
    op.drop_constraint(ACTIVE_VERSION_FK, "policies", type_="foreignkey")
    op.drop_column("policies", "active_version_id")
    op.drop_index(op.f("ix_policy_versions_policy_id"), table_name="policy_versions")
    op.drop_index(op.f("ix_policy_versions_created_at"), table_name="policy_versions")
    op.drop_table("policy_versions")
