"""add user credentials and active state

Revision ID: b73c6cb6e54a
Revises: 3e81fa4d59d2
Create Date: 2026-08-05

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b73c6cb6e54a"
down_revision: str | Sequence[str] | None = "3e81fa4d59d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.alter_column("users", "is_active", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "is_active")
    op.drop_column("users", "hashed_password")
