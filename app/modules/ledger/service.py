from sqlalchemy.orm import Session

from app.modules.ledger.enums import LedgerAccount, LedgerEntrySide, LedgerEventType
from app.modules.ledger.exceptions import LedgerIntegrityError
from app.modules.ledger.model import JournalEntry, LedgerEntry
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
