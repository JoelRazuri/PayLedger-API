"""create payments table

Revision ID: c4d8e9f0a1b2
Revises: b73c6cb6e54a
Create Date: 2026-08-06

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "c4d8e9f0a1b2"
down_revision: str | Sequence[str] | None = "b73c6cb6e54a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

payment_currency = postgresql.ENUM(
    "ARS", "USD", name="payment_currency", create_type=False
)
payment_provider = postgresql.ENUM(
    "mercado_pago", "uala", "stripe", name="payment_provider", create_type=False
)
payment_status = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "rejected",
    "failed",
    "cancelled",
    name="payment_status",
    create_type=False,
)
recipient_account_type = postgresql.ENUM(
    "bank_account",
    "virtual_wallet",
    "provider_account",
    name="recipient_account_type",
    create_type=False,
)


def _create_enum(enum: postgresql.ENUM) -> None:
    enum.create(op.get_bind(), checkfirst=True)


def _drop_enum(enum: postgresql.ENUM) -> None:
    enum.drop(op.get_bind(), checkfirst=True)


def upgrade() -> None:
    for enum in (
        payment_currency,
        payment_provider,
        payment_status,
        recipient_account_type,
    ):
        _create_enum(enum)

    op.create_table(
        "payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", payment_currency, nullable=False),
        sa.Column("provider", payment_provider, nullable=False),
        sa.Column(
            "status",
            payment_status,
            nullable=False,
            server_default="pending",
        ),
        sa.Column("recipient_name", sa.String(length=255), nullable=False),
        sa.Column(
            "recipient_account_type",
            recipient_account_type,
            nullable=False,
        ),
        sa.Column("recipient_reference", sa.String(length=255), nullable=False),
        sa.Column("recipient_description", sa.String(length=500), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("failure_message", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_payments_owner_idempotency_key",
        ),
    )
    op.create_index(
        "ix_payments_owner_created_at", "payments", ["owner_id", "created_at"]
    )
    op.create_index("ix_payments_owner_status", "payments", ["owner_id", "status"])
    op.create_index("ix_payments_owner_provider", "payments", ["owner_id", "provider"])
    op.create_index("ix_payments_owner_currency", "payments", ["owner_id", "currency"])


def downgrade() -> None:
    op.drop_index("ix_payments_owner_currency", table_name="payments")
    op.drop_index("ix_payments_owner_provider", table_name="payments")
    op.drop_index("ix_payments_owner_status", table_name="payments")
    op.drop_index("ix_payments_owner_created_at", table_name="payments")
    op.drop_table("payments")

    for enum in (
        recipient_account_type,
        payment_status,
        payment_provider,
        payment_currency,
    ):
        _drop_enum(enum)
