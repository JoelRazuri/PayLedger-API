from datetime import UTC

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, selectinload

from app.modules.ledger.enums import LedgerAccount, LedgerEntrySide, LedgerEventType
from app.modules.ledger.exceptions import LedgerIntegrityError, LedgerNotFoundError
from app.modules.ledger.model import JournalEntry, LedgerEntry
from app.modules.ledger.schema import LedgerListQuery
from app.modules.payments.enums import PaymentStatus
from app.modules.payments.model import Payment


def record_completed_payment(db: Session, payment: Payment) -> JournalEntry:
    if payment.status is not PaymentStatus.COMPLETED or payment.processed_at is None:
        raise LedgerIntegrityError(
            "Only completed payments with a processed time journalize"
        )

    journal = JournalEntry(
        payment_id=payment.id,
        event_type=LedgerEventType.PAYMENT_COMPLETED,
        amount=payment.amount,
        currency=payment.currency,
        occurred_at=payment.processed_at,
        entries=[
            LedgerEntry(
                side=LedgerEntrySide.DEBIT,
                account=LedgerAccount.PAYMENT_EXPENSE,
                amount=payment.amount,
                currency=payment.currency,
            ),
            LedgerEntry(
                side=LedgerEntrySide.CREDIT,
                account=LedgerAccount.EXTERNAL_FUNDS,
                amount=payment.amount,
                currency=payment.currency,
            ),
        ],
    )
    db.add(journal)
    db.flush()
    return journal


def list_journals(
    db: Session, owner_id: int, filters: LedgerListQuery
) -> list[JournalEntry]:
    statement = _owner_statement(owner_id)
    if filters.currency is not None:
        statement = statement.where(JournalEntry.currency == filters.currency)
    if filters.account is not None:
        statement = statement.where(
            exists().where(
                LedgerEntry.journal_entry_id == JournalEntry.id,
                LedgerEntry.account == filters.account,
            )
        )
    journals = list(
        db.scalars(
            statement.order_by(JournalEntry.occurred_at.desc(), JournalEntry.id.desc())
            .offset(filters.offset)
            .limit(filters.limit)
        ).all()
    )
    return [_normalize_journal_timestamps(journal) for journal in journals]


def get_journal(db: Session, owner_id: int, journal_id: int) -> JournalEntry:
    journal = db.scalars(
        _owner_statement(owner_id).where(JournalEntry.id == journal_id)
    ).first()
    if journal is None:
        raise LedgerNotFoundError
    return _normalize_journal_timestamps(journal)


def get_payment_journal(db: Session, owner_id: int, payment_id: int) -> JournalEntry:
    journal = db.scalars(
        _owner_statement(owner_id).where(JournalEntry.payment_id == payment_id)
    ).first()
    if journal is None:
        raise LedgerNotFoundError
    return _normalize_journal_timestamps(journal)


def _normalize_journal_timestamps(journal: JournalEntry) -> JournalEntry:
    journal.occurred_at = journal.occurred_at.astimezone(UTC)
    journal.created_at = journal.created_at.astimezone(UTC)
    return journal


def _owner_statement(owner_id: int):
    return (
        select(JournalEntry)
        .join(Payment, JournalEntry.payment_id == Payment.id)
        .where(Payment.owner_id == owner_id)
        .options(selectinload(JournalEntry.entries))
        .distinct()
    )
