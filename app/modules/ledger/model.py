from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeAlias

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.ledger.enums import LedgerAccount, LedgerEntrySide, LedgerEventType
from app.modules.payments.enums import Currency

LedgerEnum: TypeAlias = (
    type[Currency] | type[LedgerAccount] | type[LedgerEntrySide] | type[LedgerEventType]
)


def _enum_values(enum_class: LedgerEnum) -> Sequence[str]:
    return [member.value for member in enum_class]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class JournalEntry(Base):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT"), nullable=False
    )
    event_type: Mapped[LedgerEventType] = mapped_column(
        ENUM(
            LedgerEventType,
            name="ledger_event_type",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        ENUM(
            Currency,
            name="payment_currency",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )
    entries: Mapped[list["LedgerEntry"]] = relationship(back_populates="journal")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_journal_entries_amount_positive"),
        UniqueConstraint(
            "payment_id",
            "event_type",
            name="uq_journal_entries_payment_event",
        ),
        Index("ix_journal_entries_occurred_at_id", "occurred_at", "id"),
        Index("ix_journal_entries_payment_event", "payment_id", "event_type"),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    journal_entry_id: Mapped[int] = mapped_column(
        ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=False
    )
    side: Mapped[LedgerEntrySide] = mapped_column(
        ENUM(
            LedgerEntrySide,
            name="ledger_entry_side",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    account: Mapped[LedgerAccount] = mapped_column(
        ENUM(
            LedgerAccount,
            name="ledger_account",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        ENUM(
            Currency,
            name="payment_currency",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    journal: Mapped[JournalEntry] = relationship(back_populates="entries")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_ledger_entries_amount_positive"),
        CheckConstraint("side IN ('debit', 'credit')", name="ck_ledger_entries_side"),
        CheckConstraint(
            "account IN ('PAYMENT_EXPENSE', 'EXTERNAL_FUNDS')",
            name="ck_ledger_entries_account",
        ),
        UniqueConstraint(
            "journal_entry_id",
            "side",
            name="uq_ledger_entries_journal_side",
        ),
        Index("ix_ledger_entries_journal_side", "journal_entry_id", "side"),
        Index("ix_ledger_entries_account_journal", "account", "journal_entry_id"),
    )
