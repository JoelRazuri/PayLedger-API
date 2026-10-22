from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.audit.model import AuditEvent
from app.modules.payments.enums import (
    Currency,
    PaymentProcessScenario,
    PaymentProvider,
    PaymentStatus,
)
from app.modules.payments.exceptions import (
    PaymentIdempotencyConflictError,
    PaymentNotFoundError,
    PaymentStateConflictError,
)
from app.modules.payments.model import Payment
from app.modules.payments.provider import PaymentProviderInput, ProviderResult
from app.modules.payments.schema import PaymentCreate, PaymentListQuery
from app.modules.payments.service import (
    cancel_payment,
    create_payment,
    get_payment,
    list_payments,
    payment_fingerprint,
    process_payment,
)


def payment_request(amount: str = "12.50") -> PaymentCreate:
    return PaymentCreate.model_validate(
        {
            "amount": amount,
            "currency": "ARS",
            "provider": "mercado_pago",
            "recipient": {
                "name": "Ada Lovelace",
                "account_type": "bank_account",
                "reference": "CBU-123",
            },
        }
    )


def test_create_payment_persists_pending_snapshot() -> None:
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.first.return_value = None

    result = create_payment(
        db,
        owner_id=7,
        idempotency_key="key-1",
        request=payment_request(),
    )

    assert result.replayed is False
    assert result.payment.owner_id == 7
    assert result.payment.status is PaymentStatus.PENDING
    assert result.payment.amount == Decimal("12.50")
    assert result.payment.recipient_reference == "CBU-123"
    assert db.add.call_args_list[0].args == (result.payment,)
    assert isinstance(db.add.call_args_list[1].args[0], AuditEvent)
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(result.payment)


def test_create_payment_replays_identical_request_without_second_insert() -> None:
    db = MagicMock(spec=Session)
    request = payment_request("12.5")
    existing = Payment(id=4, owner_id=7, idempotency_key="key-1")
    existing.request_fingerprint = payment_fingerprint(request)
    db.query.return_value.filter.return_value.first.return_value = existing

    result = create_payment(db, owner_id=7, idempotency_key="key-1", request=request)

    assert result.payment is existing
    assert result.replayed is True
    assert isinstance(db.add.call_args.args[0], AuditEvent)
    db.commit.assert_called_once_with()


def test_create_payment_rejects_different_payload_for_reused_owner_key() -> None:
    db = MagicMock(spec=Session)
    existing = Payment(id=4, owner_id=7, idempotency_key="key-1")
    existing.request_fingerprint = payment_fingerprint(payment_request("12.50"))
    db.query.return_value.filter.return_value.first.return_value = existing

    with pytest.raises(PaymentIdempotencyConflictError):
        create_payment(
            db,
            owner_id=7,
            idempotency_key="key-1",
            request=payment_request("20"),
        )

    event = db.add.call_args.args[0]
    assert isinstance(event, AuditEvent)
    assert event.reason_code == "idempotency_conflict"


def test_create_payment_allows_the_same_key_for_another_owner() -> None:
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.first.return_value = None
    request = payment_request()

    first = create_payment(db, owner_id=7, idempotency_key="key-1", request=request)
    second = create_payment(db, owner_id=8, idempotency_key="key-1", request=request)

    assert first.payment.owner_id == 7
    assert second.payment.owner_id == 8
    assert first.payment.idempotency_key == second.payment.idempotency_key == "key-1"


def test_create_payment_rolls_back_unique_race_and_replays_winner() -> None:
    db = MagicMock(spec=Session)
    request = payment_request()
    winner = Payment(id=5, owner_id=7, idempotency_key="key-1")
    winner.request_fingerprint = payment_fingerprint(request)
    db.query.return_value.filter.return_value.first.side_effect = [None, winner]
    db.commit.side_effect = [IntegrityError("insert", {}, Exception("duplicate")), None]

    result = create_payment(db, owner_id=7, idempotency_key="key-1", request=request)

    assert result.payment is winner
    assert result.replayed is True
    db.rollback.assert_called_once_with()


def test_payment_fingerprint_normalizes_decimal() -> None:
    assert payment_fingerprint(payment_request("12.5")) == payment_fingerprint(
        payment_request("12.50")
    )


def test_get_and_list_are_owner_scoped_with_filters_and_pagination() -> None:
    db = MagicMock(spec=Session)
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value = query
    query.offset.return_value = query
    query.limit.return_value = query
    expected = [Payment(id=3, owner_id=7), Payment(id=2, owner_id=7)]
    query.all.return_value = expected

    listed = list_payments(
        db,
        owner_id=7,
        filters=PaymentListQuery(
            limit=2,
            offset=1,
            status=PaymentStatus.PENDING,
            provider=PaymentProvider.MERCADO_PAGO,
            currency=Currency.ARS,
        ),
    )

    assert listed == expected
    assert query.filter.call_count == 4
    query.offset.assert_called_once_with(1)
    query.limit.assert_called_once_with(2)

    query.filter.return_value.first.return_value = None
    with pytest.raises(PaymentNotFoundError):
        get_payment(db, owner_id=7, payment_id=999)


def test_process_claims_then_persists_controlled_provider_result() -> None:
    db = MagicMock(spec=Session)
    pending = Payment(id=4, owner_id=7, status=PaymentStatus.PENDING)
    claimed = Payment(id=4, owner_id=7, status=PaymentStatus.PROCESSING)
    db.query.return_value.filter.return_value.first.return_value = pending
    claim_result = MagicMock()
    claim_result.scalar_one_or_none.return_value = 4
    finalization_result = MagicMock()
    finalization_result.scalar_one_or_none.return_value = claimed
    db.execute.side_effect = [claim_result, finalization_result]
    provider = MagicMock()
    provider.process.return_value = ProviderResult(
        status=PaymentStatus.REJECTED,
        failure_code="business_rejection",
        failure_message="Rejected by sandbox",
    )

    payment = process_payment(
        db,
        owner_id=7,
        payment_id=4,
        scenario=PaymentProcessScenario.BUSINESS_REJECTION,
        provider=provider,
    )

    assert payment.status is PaymentStatus.REJECTED
    assert payment.failure_code == "business_rejection"
    assert payment.processed_at is not None
    provider.process.assert_called_once_with(
        PaymentProviderInput(payment_id=4),
        PaymentProcessScenario.BUSINESS_REJECTION,
    )
    assert db.commit.call_count == 2


@pytest.mark.parametrize("action", ["process", "cancel"])
def test_unavailable_lifecycle_action_keeps_existing_state(action: str) -> None:
    db = MagicMock(spec=Session)
    payment = Payment(id=4, owner_id=7, status=PaymentStatus.COMPLETED)
    db.query.return_value.filter.return_value.first.return_value = payment
    db.execute.return_value.scalar_one_or_none.return_value = None

    with pytest.raises(PaymentStateConflictError):
        if action == "process":
            process_payment(
                db,
                owner_id=7,
                payment_id=4,
                scenario=PaymentProcessScenario.SUCCESS,
                provider=MagicMock(),
            )
        else:
            cancel_payment(db, owner_id=7, payment_id=4)

    assert payment.status is PaymentStatus.COMPLETED
    assert db.add.call_args.args[0].reason_code == "state_conflict"


def test_provider_interruption_leaves_committed_claim_processing() -> None:
    db = MagicMock(spec=Session)
    pending = Payment(id=4, owner_id=7, status=PaymentStatus.PENDING)
    claimed = Payment(id=4, owner_id=7, status=PaymentStatus.PROCESSING)
    db.query.return_value.filter.return_value.first.return_value = pending
    db.execute.return_value.scalar_one_or_none.return_value = claimed
    provider = MagicMock()
    provider.process.side_effect = RuntimeError("provider interrupted")

    with pytest.raises(RuntimeError, match="provider interrupted"):
        process_payment(
            db,
            owner_id=7,
            payment_id=4,
            scenario=PaymentProcessScenario.SUCCESS,
            provider=provider,
        )

    assert claimed.status is PaymentStatus.PROCESSING
    db.commit.assert_called_once_with()
