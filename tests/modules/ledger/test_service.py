from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.modules.ledger.enums import LedgerAccount, LedgerEntrySide, LedgerEventType
from app.modules.ledger.service import record_completed_payment
from app.modules.payments.enums import Currency, PaymentStatus
from app.modules.payments.model import Payment


def test_record_completed_payment_flushes_one_balanced_journal() -> None:
    db = MagicMock(spec=Session)
    payment = Payment(
        id=8,
        amount=Decimal("12.50"),
        currency=Currency.ARS,
        status=PaymentStatus.COMPLETED,
        processed_at=datetime(2026, 8, 20, tzinfo=UTC),
    )

    journal = record_completed_payment(db, payment)

    assert journal.payment_id == 8
    assert journal.event_type is LedgerEventType.PAYMENT_COMPLETED
    assert journal.amount == Decimal("12.50")
    assert journal.currency is Currency.ARS
    assert journal.occurred_at == datetime(2026, 8, 20, tzinfo=UTC)
    entries = [
        (entry.side, entry.account, entry.amount, entry.currency)
        for entry in journal.entries
    ]
    assert entries == [
        (
            LedgerEntrySide.DEBIT,
            LedgerAccount.PAYMENT_EXPENSE,
            Decimal("12.50"),
            Currency.ARS,
        ),
        (
            LedgerEntrySide.CREDIT,
            LedgerAccount.EXTERNAL_FUNDS,
            Decimal("12.50"),
            Currency.ARS,
        ),
    ]
    db.add.assert_called_once_with(journal)
    db.flush.assert_called_once_with()
    db.commit.assert_not_called()
