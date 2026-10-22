from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.audit.enums import AuditAction, AuditOutcome, AuditResourceType
from app.modules.audit.model import AuditEvent
from app.modules.payments.enums import Currency, PaymentProvider, PaymentStatus
from app.modules.payments.model import Payment
from app.modules.reconciliation.enums import ReconciliationResult
from app.modules.reconciliation.exceptions import (
    ExternalTransactionConflictError,
    ExternalTransactionNotFoundError,
    ReconciliationConflictError,
    ReconciliationNotFoundError,
)
from app.modules.reconciliation.model import ExternalTransaction, Reconciliation
from app.modules.reconciliation.schema import (
    ExternalTransactionCreate,
    ExternalTransactionListQuery,
    ReconciliationListQuery,
)
from app.modules.reconciliation.service import (
    ExternalTransactionCreation,
    ReconciliationCreation,
    create_external_transaction,
    create_reconciliation,
    external_transaction_fingerprint,
    get_external_transaction,
    get_reconciliation,
    list_external_transactions,
    list_reconciliations,
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
    db.add.assert_any_call(created.external_transaction)
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
    assert db.add.call_count == 2


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
    db.commit.assert_called_once_with()


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


def test_reconciliation_service_public_surface_is_available() -> None:
    from app.modules.reconciliation.service import create_reconciliation

    assert callable(create_reconciliation)


def _external_transaction(identifier: int = 4) -> ExternalTransaction:
    return ExternalTransaction(
        id=identifier,
        owner_id=7,
        provider=PaymentProvider.STRIPE,
        external_id=f"event-{identifier}",
        provider_payment_id=f"payment-{identifier}",
        request_fingerprint="f" * 64,
        amount=Decimal("12.50"),
        currency=Currency.ARS,
        status=PaymentStatus.COMPLETED,
        occurred_at=datetime(2026, 9, 10, 15, 0, tzinfo=UTC),
    )


def _payment(*, currency: Currency = Currency.ARS) -> Payment:
    return Payment(
        id=9,
        owner_id=7,
        provider=PaymentProvider.STRIPE,
        provider_payment_id="payment-4",
        amount=Decimal("12.50"),
        currency=currency,
        status=PaymentStatus.COMPLETED,
    )


def _reconciliation_db(
    external: ExternalTransaction, payment: Payment | None
) -> MagicMock:
    db = MagicMock(spec=Session)
    reconciliation_query = MagicMock()
    external_query = MagicMock()
    payment_query = MagicMock()
    reconciliation_query.filter.return_value = reconciliation_query
    external_query.filter.return_value = external_query
    payment_query.filter.return_value = payment_query
    reconciliation_query.first.return_value = None
    external_query.first.return_value = external
    payment_query.first.return_value = payment
    db.query.side_effect = [reconciliation_query, external_query, payment_query]
    return db


def test_create_reconciliation_snapshots_exact_decimal_and_enum_match() -> None:
    external = _external_transaction()
    db = _reconciliation_db(external, _payment())

    created = create_reconciliation(db, 7, external.id, "match")

    assert created.replayed is False
    assert created.reconciliation.result is ReconciliationResult.MATCHED
    assert (
        created.reconciliation.amount_matches,
        created.reconciliation.currency_matches,
        created.reconciliation.status_matches,
    ) == (True, True, True)
    assert created.reconciliation.local_amount == Decimal("12.50")
    assert created.reconciliation.local_currency is Currency.ARS
    assert created.reconciliation.local_status is PaymentStatus.COMPLETED


def test_create_reconciliation_marks_currency_only_difference_mismatched() -> None:
    external = _external_transaction()
    db = _reconciliation_db(external, _payment(currency=Currency.USD))

    created = create_reconciliation(db, 7, external.id, "currency")

    assert created.reconciliation.result is ReconciliationResult.MISMATCHED
    assert (
        created.reconciliation.amount_matches,
        created.reconciliation.currency_matches,
        created.reconciliation.status_matches,
    ) == (True, False, True)


def test_create_reconciliation_keeps_unmatched_local_snapshots_and_flags_null() -> None:
    external = _external_transaction()
    db = _reconciliation_db(external, None)

    created = create_reconciliation(db, 7, external.id, "unmatched")

    assert created.reconciliation.result is ReconciliationResult.UNMATCHED
    assert created.reconciliation.payment_id is None
    assert (
        created.reconciliation.local_amount,
        created.reconciliation.local_currency,
        created.reconciliation.local_status,
        created.reconciliation.amount_matches,
        created.reconciliation.currency_matches,
        created.reconciliation.status_matches,
    ) == (None, None, None, None, None, None)


def test_reconciliation_replay_conflict_list_and_detail_are_owner_scoped() -> None:
    existing = Reconciliation(id=12, owner_id=7, external_transaction_id=4)
    db = MagicMock(spec=Session)
    replay_query = MagicMock()
    replay_query.filter.return_value = replay_query
    replay_query.first.return_value = existing
    db.query.return_value = replay_query

    assert create_reconciliation(db, 7, 4, "same") == ReconciliationCreation(
        existing, replayed=True
    )
    with pytest.raises(ReconciliationConflictError):
        create_reconciliation(db, 7, 5, "same")

    list_query = MagicMock()
    list_query.filter.return_value = list_query
    list_query.order_by.return_value = list_query
    list_query.offset.return_value = list_query
    list_query.limit.return_value = list_query
    list_query.all.return_value = [Reconciliation(id=3), Reconciliation(id=2)]
    detail_query = MagicMock()
    detail_query.filter.return_value = detail_query
    detail_query.first.return_value = None
    db.query.side_effect = [list_query, detail_query]

    listed = list_reconciliations(
        db,
        7,
        ReconciliationListQuery(result=ReconciliationResult.MATCHED, limit=2, offset=1),
    )

    assert [value.id for value in listed] == [3, 2]
    list_query.offset.assert_called_once_with(1)
    list_query.limit.assert_called_once_with(2)
    with pytest.raises(ReconciliationNotFoundError):
        get_reconciliation(db, 7, 999)


def test_external_transaction_audits_create_replay_and_conflict() -> None:
    db = MagicMock(spec=Session)
    query = db.query.return_value
    query.filter.return_value = query
    query.first.return_value = None

    created = create_external_transaction(db, owner_id=7, request=request())

    created_event = db.add.call_args_list[-1].args[0]
    assert isinstance(created_event, AuditEvent)
    assert (
        created_event.action,
        created_event.resource_type,
        created_event.resource_id,
        created_event.outcome,
        created_event.details,
    ) == (
        AuditAction.EXTERNAL_TRANSACTION_INGEST,
        AuditResourceType.EXTERNAL_TRANSACTION,
        created.external_transaction.id,
        AuditOutcome.SUCCESS,
        {},
    )

    existing = ExternalTransaction(id=4, owner_id=7)
    existing.request_fingerprint = external_transaction_fingerprint(request())
    query.first.return_value = existing
    replay = create_external_transaction(db, owner_id=7, request=request())

    replay_event = db.add.call_args_list[-1].args[0]
    assert replay.replayed is True
    assert replay_event.details == {"replayed": True}

    with pytest.raises(ExternalTransactionConflictError):
        create_external_transaction(db, owner_id=7, request=request(amount="20.00"))

    failure_event = db.add.call_args_list[-1].args[0]
    assert (failure_event.outcome, failure_event.reason_code) == (
        AuditOutcome.FAILURE,
        "idempotency_conflict",
    )
    assert db.rollback.called


def test_reconciliation_audits_results_replay_and_conflict() -> None:
    external = _external_transaction()
    db = _reconciliation_db(external, _payment())

    created = create_reconciliation(db, 7, external.id, "match")

    created_event = db.add.call_args_list[-1].args[0]
    assert isinstance(created_event, AuditEvent)
    assert (
        created_event.action,
        created_event.resource_type,
        created_event.resource_id,
        created_event.outcome,
        created_event.details,
    ) == (
        AuditAction.RECONCILIATION_EXECUTE,
        AuditResourceType.RECONCILIATION,
        created.reconciliation.id,
        AuditOutcome.SUCCESS,
        {"result": "matched"},
    )

    replay_db = MagicMock(spec=Session)
    replay_query = replay_db.query.return_value
    replay_query.filter.return_value = replay_query
    replay_query.first.return_value = created.reconciliation
    replay = create_reconciliation(replay_db, 7, external.id, "match")
    replay_event = replay_db.add.call_args_list[-1].args[0]
    assert replay.replayed is True
    assert replay_event.details == {"replayed": True}

    with pytest.raises(ReconciliationConflictError):
        create_reconciliation(replay_db, 7, external.id + 1, "match")

    failure_event = replay_db.add.call_args_list[-1].args[0]
    assert (failure_event.outcome, failure_event.reason_code) == (
        AuditOutcome.FAILURE,
        "idempotency_conflict",
    )
