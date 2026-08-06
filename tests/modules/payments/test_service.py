from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.payments.enums import Currency, PaymentProvider, PaymentStatus
from app.modules.payments.exceptions import (
    PaymentIdempotencyConflictError,
    PaymentNotFoundError,
)
from app.modules.payments.model import Payment
from app.modules.payments.schema import PaymentCreate, PaymentListQuery
from app.modules.payments.service import (
    create_payment,
    get_payment,
    list_payments,
    payment_fingerprint,
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
    db.add.assert_called_once_with(result.payment)
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
    db.add.assert_not_called()
    db.commit.assert_not_called()


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

    db.add.assert_not_called()


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
    db.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate"))

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
