from datetime import UTC
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.reconciliation.exceptions import (
    ExternalTransactionConflictError,
    ExternalTransactionNotFoundError,
)
from app.modules.reconciliation.model import ExternalTransaction
from app.modules.reconciliation.schema import (
    ExternalTransactionCreate,
    ExternalTransactionListQuery,
)
from app.modules.reconciliation.service import (
    ExternalTransactionCreation,
    create_external_transaction,
    external_transaction_fingerprint,
    get_external_transaction,
    list_external_transactions,
)


def request(**overrides: object) -> ExternalTransactionCreate:
    payload: dict[str, object] = {
        "provider": "stripe",
        "external_id": " event-1 ",
        "provider_payment_id": " payment-1 ",
        "amount": "12.50",
        "currency": "ARS",
        "status": "completed",
        "occurred_at": "2026-09-10T12:00:00.123456-03:00",
    }
    payload.update(overrides)
    return ExternalTransactionCreate.model_validate(payload)


def test_external_fingerprint_normalizes_offset_and_trimmed_identifiers() -> None:
    offset_request = request()
    utc_request = request(
        external_id="event-1",
        provider_payment_id="payment-1",
        occurred_at="2026-09-10T15:00:00.123456Z",
    )

    assert external_transaction_fingerprint(offset_request) == (
        external_transaction_fingerprint(utc_request)
    )


def test_create_external_transaction_persists_normalized_evidence() -> None:
    db = MagicMock(spec=Session)
    query = db.query.return_value
    query.filter.return_value = query
    query.first.return_value = None

    created = create_external_transaction(db, owner_id=7, request=request())

    assert created.replayed is False
    assert created.external_transaction.owner_id == 7
    assert created.external_transaction.external_id == "event-1"
    assert created.external_transaction.occurred_at.tzinfo is UTC
    db.add.assert_called_once_with(created.external_transaction)
    db.flush.assert_called_once_with()
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(created.external_transaction)


def test_create_external_transaction_replays_or_conflicts_existing_evidence() -> None:
    db = MagicMock(spec=Session)
    query = db.query.return_value
    query.filter.return_value = query
    existing = ExternalTransaction(id=4, owner_id=7)
    existing.request_fingerprint = external_transaction_fingerprint(request())
    query.first.return_value = existing

    replay = create_external_transaction(db, owner_id=7, request=request())

    assert replay == ExternalTransactionCreation(existing, replayed=True)
    with pytest.raises(ExternalTransactionConflictError):
        create_external_transaction(db, owner_id=7, request=request(amount="20.00"))
    db.add.assert_not_called()


def test_create_external_transaction_recovers_only_named_unique_race() -> None:
    class DuplicateReferenceError(Exception):
        diag = MagicMock(
            constraint_name="uq_external_transactions_owner_provider_external_id"
        )

    db = MagicMock(spec=Session)
    query = db.query.return_value
    query.filter.return_value = query
    winner = ExternalTransaction(id=5, owner_id=7)
    winner.request_fingerprint = external_transaction_fingerprint(request())
    query.first.side_effect = [None, winner]
    db.flush.side_effect = IntegrityError("insert", {}, DuplicateReferenceError())

    replay = create_external_transaction(db, owner_id=7, request=request())

    assert replay == ExternalTransactionCreation(winner, replayed=True)
    db.commit.assert_not_called()


def test_get_and_list_external_transactions_are_owner_scoped_and_stable() -> None:
    db = MagicMock(spec=Session)
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value = query
    query.offset.return_value = query
    query.limit.return_value = query
    query.all.return_value = [ExternalTransaction(id=3), ExternalTransaction(id=2)]

    listed = list_external_transactions(
        db, owner_id=7, filters=ExternalTransactionListQuery(limit=2, offset=1)
    )

    assert [item.id for item in listed] == [3, 2]
    query.offset.assert_called_once_with(1)
    query.limit.assert_called_once_with(2)
    query.filter.return_value.first.return_value = None
    with pytest.raises(ExternalTransactionNotFoundError):
        get_external_transaction(db, owner_id=7, external_transaction_id=999)
