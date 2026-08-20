"""create ledger tables

Revision ID: e8a1d5f3c9b4
Revises: c4d8e9f0a1b2
Create Date: 2026-08-20

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "e8a1d5f3c9b4"
down_revision: str | Sequence[str] | None = "c4d8e9f0a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ledger_event_type = postgresql.ENUM(
    "payment_completed", name="ledger_event_type", create_type=False
)
ledger_entry_side = postgresql.ENUM(
    "debit", "credit", name="ledger_entry_side", create_type=False
)
ledger_account = postgresql.ENUM(
    "PAYMENT_EXPENSE", "EXTERNAL_FUNDS", name="ledger_account", create_type=False
)
payment_currency = postgresql.ENUM(
    "ARS", "USD", name="payment_currency", create_type=False
)


def _create_enum(enum: postgresql.ENUM) -> None:
    enum.create(op.get_bind(), checkfirst=True)


def _drop_enum(enum: postgresql.ENUM) -> None:
    enum.drop(op.get_bind(), checkfirst=True)


def upgrade() -> None:
    for enum in (ledger_event_type, ledger_entry_side, ledger_account):
        _create_enum(enum)

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.Integer(), nullable=False),
        sa.Column("event_type", ledger_event_type, nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", payment_currency, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint("amount > 0", name="ck_journal_entries_amount_positive"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "payment_id", "event_type", name="uq_journal_entries_payment_event"
        ),
    )
    op.create_index(
        "ix_journal_entries_occurred_at_id", "journal_entries", ["occurred_at", "id"]
    )
    op.create_index(
        "ix_journal_entries_payment_event",
        "journal_entries",
        ["payment_id", "event_type"],
    )

    op.create_table(
        "ledger_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("journal_entry_id", sa.Integer(), nullable=False),
        sa.Column("side", ledger_entry_side, nullable=False),
        sa.Column("account", ledger_account, nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", payment_currency, nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_ledger_entries_amount_positive"),
        sa.CheckConstraint(
            "side IN ('debit', 'credit')", name="ck_ledger_entries_side"
        ),
        sa.CheckConstraint(
            "account IN ('PAYMENT_EXPENSE', 'EXTERNAL_FUNDS')",
            name="ck_ledger_entries_account",
        ),
        sa.ForeignKeyConstraint(
            ["journal_entry_id"], ["journal_entries.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "journal_entry_id", "side", name="uq_ledger_entries_journal_side"
        ),
    )
    op.create_index(
        "ix_ledger_entries_journal_side", "ledger_entries", ["journal_entry_id", "side"]
    )
    op.create_index(
        "ix_ledger_entries_account_journal",
        "ledger_entries",
        ["account", "journal_entry_id"],
    )

    op.execute(
        """
        CREATE FUNCTION validate_ledger_journal_balance()
        RETURNS trigger AS $$
        DECLARE
            checked_journal_id integer;
            journal_amount numeric(18, 2);
            journal_currency payment_currency;
            entry_count integer;
            debit_count integer;
            credit_count integer;
            net_amount numeric(18, 2);
        BEGIN
            IF TG_TABLE_NAME = 'journal_entries' THEN
                checked_journal_id := COALESCE(NEW.id, OLD.id);
            ELSE
                checked_journal_id := COALESCE(
                    NEW.journal_entry_id,
                    OLD.journal_entry_id
                );
            END IF;

            SELECT amount, currency
            INTO journal_amount, journal_currency
            FROM journal_entries
            WHERE id = checked_journal_id;

            IF NOT FOUND THEN
                RETURN NULL;
            END IF;

            SELECT
                count(*),
                count(*) FILTER (WHERE side = 'debit'),
                count(*) FILTER (WHERE side = 'credit'),
                COALESCE(
                    sum(CASE WHEN side = 'debit' THEN amount ELSE -amount END),
                    0
                )
            INTO entry_count, debit_count, credit_count, net_amount
            FROM ledger_entries
            WHERE journal_entry_id = checked_journal_id;

            IF entry_count <> 2 OR debit_count <> 1 OR credit_count <> 1
                OR net_amount <> 0
                OR EXISTS (
                    SELECT 1
                    FROM ledger_entries
                    WHERE journal_entry_id = checked_journal_id
                      AND (amount <> journal_amount OR currency <> journal_currency)
                )
            THEN
                RAISE EXCEPTION 'ledger journal % must have balanced postings',
                    checked_journal_id
                    USING ERRCODE = '23514';
            END IF;

            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER journal_entries_balance_check
        AFTER INSERT OR UPDATE OR DELETE ON journal_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_ledger_journal_balance();
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ledger_entries_balance_check
        AFTER INSERT OR UPDATE OR DELETE ON ledger_entries
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW EXECUTE FUNCTION validate_ledger_journal_balance();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER ledger_entries_balance_check ON ledger_entries")
    op.execute("DROP TRIGGER journal_entries_balance_check ON journal_entries")
    op.execute("DROP FUNCTION validate_ledger_journal_balance()")
    op.drop_index("ix_ledger_entries_account_journal", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_journal_side", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("ix_journal_entries_payment_event", table_name="journal_entries")
    op.drop_index("ix_journal_entries_occurred_at_id", table_name="journal_entries")
    op.drop_table("journal_entries")

    for enum in (ledger_account, ledger_entry_side, ledger_event_type):
        _drop_enum(enum)
