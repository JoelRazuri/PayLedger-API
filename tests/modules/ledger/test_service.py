from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

from sqlalchemy.orm import Session

from app.modules.ledger.enums import LedgerAccount, LedgerEntrySide, LedgerEventType
from app.modules.ledger.model import JournalEntry
from app.modules.ledger.schema import LedgerListQuery
from app.modules.ledger.service import (
    get_journal,
    get_payment_journal,
    list_journals,
    record_completed_payment,
)
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


def test_journal_queries_use_owner_scope_exists_filter_and_stable_ordering() -> None:
    db = MagicMock(spec=Session)
    expected = MagicMock(spec=JournalEntry)
    db.scalars.return_value.all.return_value = [expected]

    journals = list_journals(
        db,
        owner_id=7,
        filters=LedgerListQuery(
            limit=1,
            offset=2,
            currency=Currency.ARS,
            account=LedgerAccount.EXTERNAL_FUNDS,
        ),
    )

    statement = str(db.scalars.call_args.args[0])
    assert journals == [expected]
    assert "SELECT DISTINCT" in statement
    assert "JOIN payments" in statement
    assert "payments.owner_id = :owner_id_1" in statement
    assert "EXISTS (SELECT" in statement
    assert "ledger_entries.account = :account_1" in statement
    assert (
        "ORDER BY journal_entries.occurred_at DESC, journal_entries.id DESC"
        in statement
    )
    assert "LIMIT :param_1 OFFSET :param_2" in statement
    db.scalars.return_value.first.return_value = expected

    assert get_journal(db, owner_id=7, journal_id=8) is expected
    assert get_payment_journal(db, owner_id=7, payment_id=4) is expected

    statements = [str(call.args[0]) for call in db.scalars.call_args_list]
    assert all("JOIN payments" in statement for statement in statements)
    assert "journal_entries.id = :id_1" in statements[1]
    assert "journal_entries.payment_id = :payment_id_1" in statements[2]
