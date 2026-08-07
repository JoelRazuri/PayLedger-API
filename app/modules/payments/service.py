import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.payments.enums import PaymentProcessScenario, PaymentStatus
from app.modules.payments.exceptions import (
    PaymentIdempotencyConflictError,
    PaymentNotFoundError,
    PaymentStateConflictError,
)
from app.modules.payments.model import Payment
from app.modules.payments.provider import PaymentProvider, ProviderResult
from app.modules.payments.schema import PaymentCreate, PaymentListQuery


@dataclass(frozen=True)
class PaymentCreation:
    payment: Payment
    replayed: bool


def payment_fingerprint(request: PaymentCreate) -> str:
    payload = {
        "amount": f"{request.amount:.2f}",
        "currency": request.currency.value,
        "provider": request.provider.value,
        "recipient": {
            "account_type": request.recipient.account_type.value,
            "description": request.recipient.description,
            "name": request.recipient.name,
            "reference": request.recipient.reference,
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()


def create_payment(
    db: Session,
    owner_id: int,
    idempotency_key: str,
    request: PaymentCreate,
) -> PaymentCreation:
    fingerprint = payment_fingerprint(request)
    existing = _find_by_key(db, owner_id, idempotency_key)
    if existing:
        return _replay_or_conflict(existing, fingerprint)

    payment = Payment(
        owner_id=owner_id,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint,
        amount=request.amount,
        currency=request.currency,
        provider=request.provider,
        status=PaymentStatus.PENDING,
        recipient_name=request.recipient.name,
        recipient_account_type=request.recipient.account_type,
        recipient_reference=request.recipient.reference,
        recipient_description=request.recipient.description,
    )
    error = _save_payment(db, payment)
    if error:
        existing = _find_by_key(db, owner_id, idempotency_key)
        if existing:
            return _replay_or_conflict(existing, fingerprint)
        raise error
    return PaymentCreation(payment=payment, replayed=False)


def get_payment(db: Session, owner_id: int, payment_id: int) -> Payment:
    payment = _owned_query(db, owner_id).filter(Payment.id == payment_id).first()
    if payment is None:
        raise PaymentNotFoundError
    return payment


def list_payments(
    db: Session,
    owner_id: int,
    filters: PaymentListQuery,
) -> list[Payment]:
    query = _owned_query(db, owner_id)
    for column, value in (
        (Payment.status, filters.status),
        (Payment.provider, filters.provider),
        (Payment.currency, filters.currency),
    ):
        if value is not None:
            query = query.filter(column == value)
    return (
        query.order_by(Payment.created_at.desc())
        .offset(filters.offset)
        .limit(filters.limit)
        .all()
    )


def process_payment(
    db: Session,
    owner_id: int,
    payment_id: int,
    scenario: PaymentProcessScenario,
    provider: PaymentProvider,
) -> Payment:
    get_payment(db, owner_id, payment_id)
    payment = _claim_pending(db, owner_id, payment_id, PaymentStatus.PROCESSING)
    result = provider.process(payment, scenario)
    return _complete_processing(db, payment, result)


def cancel_payment(db: Session, owner_id: int, payment_id: int) -> Payment:
    get_payment(db, owner_id, payment_id)
    payment = _claim_pending(db, owner_id, payment_id, PaymentStatus.CANCELLED)
    db.refresh(payment)
    return payment


def _find_by_key(db: Session, owner_id: int, key: str) -> Payment | None:
    return (
        db.query(Payment)
        .filter(Payment.owner_id == owner_id, Payment.idempotency_key == key)
        .first()
    )


def _owned_query(db: Session, owner_id: int):
    return db.query(Payment).filter(Payment.owner_id == owner_id)


def _save_payment(db: Session, payment: Payment) -> IntegrityError | None:
    db.add(payment)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        return error
    db.refresh(payment)
    return None


def _replay_or_conflict(payment: Payment, fingerprint: str) -> PaymentCreation:
    if payment.request_fingerprint != fingerprint:
        raise PaymentIdempotencyConflictError
    return PaymentCreation(payment=payment, replayed=True)


def _claim_pending(
    db: Session,
    owner_id: int,
    payment_id: int,
    target_status: PaymentStatus,
) -> Payment:
    payment = db.execute(
        update(Payment)
        .where(
            Payment.id == payment_id,
            Payment.owner_id == owner_id,
            Payment.status == PaymentStatus.PENDING,
        )
        .values(status=target_status)
        .returning(Payment)
    ).scalar_one_or_none()
    if payment is None:
        raise PaymentStateConflictError
    db.commit()
    return payment


def _apply_provider_result(payment: Payment, result: ProviderResult) -> None:
    payment.status = result.status
    payment.provider_payment_id = result.provider_payment_id
    payment.failure_code = result.failure_code
    payment.failure_message = result.failure_message
    payment.processed_at = datetime.now(UTC)


def _complete_processing(
    db: Session,
    payment: Payment,
    result: ProviderResult,
) -> Payment:
    _apply_provider_result(payment, result)
    db.commit()
    db.refresh(payment)
    return payment
