import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.audit.enums import AuditAction, AuditOutcome, AuditResourceType
from app.modules.audit.service import AuditEventData, stage_event
from app.modules.ledger.enums import LedgerEventType
from app.modules.ledger.model import JournalEntry
from app.modules.ledger.service import record_completed_payment
from app.modules.payments.enums import PaymentProcessScenario, PaymentStatus
from app.modules.payments.exceptions import (
    PaymentIdempotencyConflictError,
    PaymentNotFoundError,
    PaymentStateConflictError,
)
from app.modules.payments.model import Payment
from app.modules.payments.provider import (
    PaymentProvider,
    PaymentProviderInput,
    ProviderResult,
)
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


def payment_audit_details(
    status: PaymentStatus | None = None, *, replayed: bool = False
) -> dict[str, object]:
    if replayed:
        return {"replayed": True}
    return {"status": status.value} if status is not None else {}


def create_payment(
    db: Session,
    owner_id: int,
    idempotency_key: str,
    request: PaymentCreate,
) -> PaymentCreation:
    fingerprint = payment_fingerprint(request)
    existing = _find_by_key(db, owner_id, idempotency_key)
    if existing:
        return _replay_or_conflict(db, owner_id, existing, fingerprint)

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
            return _replay_or_conflict(db, owner_id, existing, fingerprint)
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
    try:
        get_payment(db, owner_id, payment_id)
        provider_input = _claim_pending(
            db, owner_id, payment_id, PaymentStatus.PROCESSING
        )
    except (PaymentNotFoundError, PaymentStateConflictError) as error:
        _record_payment_failure(db, owner_id, AuditAction.PAYMENT_PROCESS, payment_id)
        raise error

    result = provider.process(provider_input, scenario)
    try:
        return _complete_processing(db, owner_id, provider_input.payment_id, result)
    except PaymentStateConflictError as error:
        _record_payment_failure(db, owner_id, AuditAction.PAYMENT_PROCESS, payment_id)
        raise error


def cancel_payment(db: Session, owner_id: int, payment_id: int) -> Payment:
    try:
        get_payment(db, owner_id, payment_id)
        claimed = _claim_pending(
            db, owner_id, payment_id, PaymentStatus.CANCELLED, commit=False
        )
        _stage_payment_event(
            db,
            owner_id,
            AuditAction.PAYMENT_CANCEL,
            claimed.payment_id,
            AuditOutcome.SUCCESS,
            PaymentStatus.CANCELLED,
        )
        db.commit()
    except (PaymentNotFoundError, PaymentStateConflictError) as error:
        _record_payment_failure(db, owner_id, AuditAction.PAYMENT_CANCEL, payment_id)
        raise error
    except Exception:
        db.rollback()
        raise
    return get_payment(db, owner_id, claimed.payment_id)


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
        db.flush()
        _stage_payment_event(
            db,
            payment.owner_id,
            AuditAction.PAYMENT_CREATE,
            payment.id,
            AuditOutcome.SUCCESS,
            PaymentStatus.PENDING,
        )
        db.commit()
    except IntegrityError as error:
        db.rollback()
        return error
    db.refresh(payment)
    return None


def _replay_or_conflict(
    db: Session, owner_id: int, payment: Payment, fingerprint: str
) -> PaymentCreation:
    if payment.request_fingerprint != fingerprint:
        _record_payment_failure(
            db,
            owner_id,
            AuditAction.PAYMENT_CREATE,
            payment.id,
            "idempotency_conflict",
        )
        raise PaymentIdempotencyConflictError
    _stage_payment_event(
        db,
        owner_id,
        AuditAction.PAYMENT_CREATE,
        payment.id,
        AuditOutcome.SUCCESS,
        replayed=True,
    )
    db.commit()
    return PaymentCreation(payment=payment, replayed=True)


def _claim_pending(
    db: Session,
    owner_id: int,
    payment_id: int,
    target_status: PaymentStatus,
    *,
    commit: bool = True,
) -> PaymentProviderInput:
    claimed_id = db.execute(
        update(Payment)
        .where(
            Payment.id == payment_id,
            Payment.owner_id == owner_id,
            Payment.status == PaymentStatus.PENDING,
        )
        .values(status=target_status)
        .returning(Payment.id)
    ).scalar_one_or_none()
    if claimed_id is None:
        raise PaymentStateConflictError
    if commit:
        db.commit()
    return PaymentProviderInput(payment_id=claimed_id)


def _apply_provider_result(payment: Payment, result: ProviderResult) -> None:
    payment.status = result.status
    payment.provider_payment_id = result.provider_payment_id
    payment.failure_code = result.failure_code
    payment.failure_message = result.failure_message
    payment.processed_at = datetime.now(UTC)


def _complete_processing(
    db: Session,
    owner_id: int,
    payment_id: int,
    result: ProviderResult,
) -> Payment:
    try:
        payment = db.execute(
            select(Payment)
            .where(Payment.id == payment_id, Payment.owner_id == owner_id)
            .with_for_update()
        ).scalar_one_or_none()
        if payment is None:
            raise PaymentStateConflictError
        if payment.status is PaymentStatus.COMPLETED:
            if result.status is PaymentStatus.COMPLETED and _completed_journal_exists(
                db, payment.id
            ):
                db.commit()
                db.refresh(payment)
                db.commit()
                return payment
            raise PaymentStateConflictError
        if payment.status is not PaymentStatus.PROCESSING:
            raise PaymentStateConflictError

        _apply_provider_result(payment, result)
        if result.status is PaymentStatus.COMPLETED:
            record_completed_payment(db, payment)
        _stage_payment_event(
            db,
            owner_id,
            AuditAction.PAYMENT_PROCESS,
            payment.id,
            (
                AuditOutcome.SUCCESS
                if result.status is PaymentStatus.COMPLETED
                else AuditOutcome.FAILURE
            ),
            result.status,
            reason_code=result.failure_code or "provider_failure",
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(payment)
    return payment


def _completed_journal_exists(db: Session, payment_id: int) -> bool:
    return (
        db.scalar(
            select(JournalEntry.id).where(
                JournalEntry.payment_id == payment_id,
                JournalEntry.event_type == LedgerEventType.PAYMENT_COMPLETED,
            )
        )
        is not None
    )


def _stage_payment_event(
    db: Session,
    owner_id: int,
    action: AuditAction,
    payment_id: int | None,
    outcome: AuditOutcome,
    status: PaymentStatus | None = None,
    *,
    replayed: bool = False,
    reason_code: str | None = None,
) -> None:
    stage_event(
        db,
        AuditEventData(
            actor_user_id=owner_id,
            action=action,
            resource_type=AuditResourceType.PAYMENT,
            resource_id=payment_id,
            outcome=outcome,
            reason_code=reason_code if outcome is AuditOutcome.FAILURE else None,
            details=payment_audit_details(status, replayed=replayed),
        ),
    )


def _record_payment_failure(
    db: Session,
    owner_id: int,
    action: AuditAction,
    payment_id: int | None,
    reason_code: str = "state_conflict",
) -> None:
    db.rollback()
    _stage_payment_event(
        db,
        owner_id,
        action,
        payment_id,
        AuditOutcome.FAILURE,
        reason_code=reason_code,
    )
    db.commit()
