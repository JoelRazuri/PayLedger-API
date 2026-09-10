"""add reconciliation tables

Revision ID: f4c4e8a1d5f3
Revises: e8a1d5f3c9b4
Create Date: 2026-09-10

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f4c4e8a1d5f3"
down_revision: str | Sequence[str] | None = "e8a1d5f3c9b4"
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
reconciliation_result = postgresql.ENUM(
    "matched",
    "mismatched",
    "unmatched",
    name="reconciliation_result",
    create_type=False,
)


def _create_enum(enum: postgresql.ENUM) -> None:
    enum.create(op.get_bind(), checkfirst=True)


def _drop_enum(enum: postgresql.ENUM) -> None:
    enum.drop(op.get_bind(), checkfirst=True)


def _duplicate_payment_references() -> list[tuple[int, str, str, int]]:
    rows = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT owner_id, provider, provider_payment_id, count(*) "
                "FROM payments "
                "WHERE provider_payment_id IS NOT NULL "
                "GROUP BY owner_id, provider, provider_payment_id "
                "HAVING count(*) > 1 "
                "ORDER BY owner_id, provider, provider_payment_id"
            )
        )
        .all()
    )
    return [
        (
            int(row.owner_id),
            str(row.provider),
            str(row.provider_payment_id),
            int(row.count),
        )
        for row in rows
    ]


def _duplicate_reference_error(rows: list[tuple[int, str, str, int]]) -> str:
    details = "; ".join(
        "owner_id="
        f"{owner_id}, provider={provider}, provider_payment_id={reference}, "
        f"count={count}"
        for owner_id, provider, reference, count in rows
    )
    return (
        "Cannot add payment provider reference uniqueness; duplicates found: " + details
    )


def upgrade() -> None:
    duplicates = _duplicate_payment_references()
    if duplicates:
        raise RuntimeError(_duplicate_reference_error(duplicates))

    _create_enum(reconciliation_result)

    op.create_table(
        "external_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("provider", payment_provider, nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=255), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", payment_currency, nullable=False),
        sa.Column("status", payment_status, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "amount > 0", name="ck_external_transactions_amount_positive"
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'rejected', 'failed', 'cancelled')",
            name="ck_external_transactions_status_terminal",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_external_transactions_owner_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "provider",
            "external_id",
            name="uq_external_transactions_owner_provider_external_id",
        ),
    )
    op.create_index(
        "ix_external_transactions_owner_received_at_id",
        "external_transactions",
        ["owner_id", "received_at", "id"],
    )

    op.create_table(
        "reconciliations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("external_transaction_id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("external_amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("external_currency", payment_currency, nullable=False),
        sa.Column("external_status", payment_status, nullable=False),
        sa.Column("local_amount", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("local_currency", payment_currency, nullable=True),
        sa.Column("local_status", payment_status, nullable=True),
        sa.Column("result", reconciliation_result, nullable=False),
        sa.Column("amount_matches", sa.Boolean(), nullable=True),
        sa.Column("currency_matches", sa.Boolean(), nullable=True),
        sa.Column("status_matches", sa.Boolean(), nullable=True),
        sa.Column(
            "reconciled_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "external_amount > 0",
            name="ck_reconciliations_external_amount_positive",
        ),
        sa.CheckConstraint(
            "(result = 'unmatched' AND payment_id IS NULL AND local_amount IS NULL AND "
            "local_currency IS NULL AND local_status IS NULL AND "
            "amount_matches IS NULL AND currency_matches IS NULL AND "
            "status_matches IS NULL) OR result != 'unmatched'",
            name="ck_reconciliations_unmatched_nulls",
        ),
        sa.CheckConstraint(
            "(result IN ('matched', 'mismatched') AND payment_id IS NOT NULL AND "
            "local_amount IS NOT NULL AND local_currency IS NOT NULL AND "
            "local_status IS NOT NULL AND "
            "amount_matches IS NOT NULL AND currency_matches IS NOT NULL AND "
            "status_matches IS NOT NULL) OR result NOT IN ('matched', 'mismatched')",
            name="ck_reconciliations_local_snapshot_required",
        ),
        sa.CheckConstraint(
            "result != 'matched' OR "
            "(amount_matches IS TRUE AND currency_matches IS TRUE AND "
            "status_matches IS TRUE)",
            name="ck_reconciliations_matched_flags",
        ),
        sa.CheckConstraint(
            "result != 'mismatched' OR "
            "(amount_matches IS FALSE OR currency_matches IS FALSE OR "
            "status_matches IS FALSE)",
            name="ck_reconciliations_mismatched_flags",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name="fk_reconciliations_owner_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["external_transaction_id"],
            ["external_transactions.id"],
            name="fk_reconciliations_external_transaction",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["payment_id"],
            ["payments.id"],
            name="fk_reconciliations_payment_id_payments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_reconciliations_owner_idempotency_key",
        ),
    )
    op.create_index(
        "ix_reconciliations_owner_reconciled_at_id",
        "reconciliations",
        ["owner_id", "reconciled_at", "id"],
    )
    op.create_index(
        "ix_reconciliations_owner_result_reconciled_at_id",
        "reconciliations",
        ["owner_id", "result", "reconciled_at", "id"],
    )
    op.create_index(
        "uq_payments_owner_provider_provider_payment_id",
        "payments",
        ["owner_id", "provider", "provider_payment_id"],
        unique=True,
        postgresql_where=sa.text("provider_payment_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_payments_owner_provider_provider_payment_id", table_name="payments"
    )
    op.drop_index(
        "ix_reconciliations_owner_result_reconciled_at_id", table_name="reconciliations"
    )
    op.drop_index(
        "ix_reconciliations_owner_reconciled_at_id", table_name="reconciliations"
    )
    op.drop_table("reconciliations")
    op.drop_index(
        "ix_external_transactions_owner_received_at_id",
        table_name="external_transactions",
    )
    op.drop_table("external_transactions")
    _drop_enum(reconciliation_result)
