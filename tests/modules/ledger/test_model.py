from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKeyConstraint,
    Numeric,
    UniqueConstraint,
)

from app.core.database import Base
from app.modules.ledger.enums import LedgerAccount, LedgerEntrySide, LedgerEventType
from app.modules.ledger.model import JournalEntry, LedgerEntry
from app.modules.payments.enums import Currency


def test_journal_entry_models_immutable_completed_payment_facts() -> None:
    table = JournalEntry.__table__

    assert table.name == "journal_entries"
    assert isinstance(table.c.amount.type, Numeric)
    assert (table.c.amount.type.precision, table.c.amount.type.scale) == (18, 2)
    assert isinstance(table.c.currency.type, Enum)
    assert table.c.currency.type.enums == ["ARS", "USD"]
    assert table.c.payment_id.nullable is False
    assert table.c.event_type.nullable is False
    assert table.c.occurred_at.type.timezone is True
    assert table.c.created_at.type.timezone is True
    assert Base.metadata.tables["journal_entries"] is table

    journal = JournalEntry(
        payment_id=7,
        event_type=LedgerEventType.PAYMENT_COMPLETED,
        amount=Decimal("42.50"),
        currency=Currency.ARS,
        occurred_at=datetime(2026, 8, 20, tzinfo=UTC),
    )

    assert journal.payment_id == 7
    assert journal.amount == Decimal("42.50")
    assert journal.currency is Currency.ARS


def test_ledger_entry_models_require_closed_vocabulary_and_relationship_keys() -> None:
    journal_table = JournalEntry.__table__
    entry_table = LedgerEntry.__table__

    assert isinstance(entry_table.c.amount.type, Numeric)
    assert (entry_table.c.amount.type.precision, entry_table.c.amount.type.scale) == (
        18,
        2,
    )
    assert entry_table.c.side.type.enums == ["debit", "credit"]
    assert entry_table.c.account.type.enums == ["PAYMENT_EXPENSE", "EXTERNAL_FUNDS"]
    assert entry_table.c.currency.type.enums == ["ARS", "USD"]
    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        and tuple(constraint.column_keys) == ("payment_id",)
        for constraint in journal_table.constraints
    )
    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        and tuple(constraint.column_keys) == ("journal_entry_id",)
        for constraint in entry_table.constraints
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns)
        == ("payment_id", "event_type")
        for constraint in journal_table.constraints
    )
    assert any(
        isinstance(constraint, UniqueConstraint)
        and tuple(column.name for column in constraint.columns)
        == ("journal_entry_id", "side")
        for constraint in entry_table.constraints
    )
    assert {
        constraint.sqltext.text
        for constraint in journal_table.constraints
        if isinstance(constraint, CheckConstraint)
    } >= {"amount > 0"}
    assert {
        constraint.sqltext.text
        for constraint in entry_table.constraints
        if isinstance(constraint, CheckConstraint)
    } >= {"amount > 0"}

    entry = LedgerEntry(
        journal_entry_id=3,
        side=LedgerEntrySide.DEBIT,
        account=LedgerAccount.PAYMENT_EXPENSE,
        amount=Decimal("42.50"),
        currency=Currency.ARS,
    )

    assert entry.side is LedgerEntrySide.DEBIT
    assert entry.account is LedgerAccount.PAYMENT_EXPENSE
