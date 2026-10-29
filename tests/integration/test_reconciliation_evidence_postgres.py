import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.core.database import get_db
from app.modules.audit.enums import AuditAction, AuditOutcome
from app.modules.audit.model import AuditEvent
from app.modules.auth.dependencies import get_current_user
from app.modules.payments.enums import (
    Currency,
    PaymentProvider,
    PaymentStatus,
    RecipientAccountType,
)
from app.modules.payments.model import Payment
from app.modules.reconciliation import router as reconciliation_router
from app.modules.reconciliation import service as reconciliation_service
from app.modules.reconciliation.model import ExternalTransaction, Reconciliation
from app.modules.reconciliation.schema import (
    ExternalTransactionCreate,
    ExternalTransactionListQuery,
)
from app.modules.reconciliation.service import (
    create_external_transaction,
    create_reconciliation,
    list_external_transactions,
)
from tests.integration.test_payments_postgres import user

pytest_plugins = ("tests.integration.test_payments_postgres",)


def _request(external_id: str, **overrides: object) -> ExternalTransactionCreate:
    payload: dict[str, object] = {
        "provider": "stripe",
        "external_id": external_id,
        "provider_payment_id": f"payment-{external_id}",
        "amount": "12.50",
        "currency": "ARS",
        "status": "completed",
        "occurred_at": "2026-09-10T12:00:00-03:00",
    }
    payload.update(overrides)
    return ExternalTransactionCreate.model_validate(payload)


def test_evidence_httpx_flow_persists_replay_conflict_and_owner_boundary(
    sessions,
) -> None:
    db = sessions()
    app = FastAPI()
    app.include_router(reconciliation_router.router)
    try:
        owner = user(db, 70)
        foreign_owner = user(db, 71)
        foreign = create_external_transaction(db, foreign_owner.id, _request("foreign"))
        app.dependency_overrides[get_current_user] = lambda: owner
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            first = client.post(
                "/external-transactions",
                json={
                    "provider": "stripe",
                    "external_id": "evidence-1",
                    "provider_payment_id": "payment-evidence-1",
                    "amount": "12.50",
                    "currency": "ARS",
                    "status": "completed",
                    "occurred_at": "2026-09-10T12:00:00-03:00",
                },
            )
            replay = client.post(
                "/external-transactions",
                json={
                    "provider": "stripe",
                    "external_id": "evidence-1",
                    "provider_payment_id": "payment-evidence-1",
                    "amount": "12.50",
                    "currency": "ARS",
                    "status": "completed",
                    "occurred_at": "2026-09-10T15:00:00Z",
                },
            )
            conflict = client.post(
                "/external-transactions",
                json={
                    "provider": "stripe",
                    "external_id": "evidence-1",
                    "provider_payment_id": "payment-evidence-1",
                    "amount": "20.00",
                    "currency": "ARS",
                    "status": "completed",
                    "occurred_at": "2026-09-10T15:00:00Z",
                },
            )
            progressive = client.post(
                "/external-transactions",
                json={
                    "provider": "stripe",
                    "external_id": "pending-1",
                    "provider_payment_id": "payment-pending-1",
                    "amount": "12.50",
                    "currency": "ARS",
                    "status": "pending",
                    "occurred_at": "2026-09-10T15:00:00Z",
                },
            )
            foreign_response = client.get(
                f"/external-transactions/{foreign.external_transaction.id}"
            )
            listed = client.get("/external-transactions?limit=20")
        events = (
            db.query(AuditEvent)
            .filter(AuditEvent.actor_user_id == owner.id)
            .order_by(AuditEvent.id)
            .all()
        )
    finally:
        app.dependency_overrides.clear()
        db.close()

    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["id"] == replay.json()["id"]
    assert first.json()["occurred_at"] == "2026-09-10T15:00:00Z"
    assert conflict.status_code == 409
    assert progressive.status_code == 422
    assert foreign_response.status_code == 404
    assert [item["external_id"] for item in listed.json()] == ["evidence-1"]
    assert [(event.action, event.outcome) for event in events] == [
        (AuditAction.EXTERNAL_TRANSACTION_INGEST, AuditOutcome.SUCCESS),
        (AuditAction.EXTERNAL_TRANSACTION_INGEST, AuditOutcome.SUCCESS),
        (AuditAction.EXTERNAL_TRANSACTION_INGEST, AuditOutcome.FAILURE),
    ]
    assert [event.details for event in events] == [{}, {"replayed": True}, {}]
    assert events[-1].reason_code == "idempotency_conflict"


def test_two_postgresql_sessions_replay_one_exact_external_transaction(
    sessions, monkeypatch
) -> None:
    setup = sessions()
    try:
        owner = user(setup, 72)
        owner_id = owner.id
    finally:
        setup.close()

    original_find = reconciliation_service._find_external_transaction
    first_reads = threading.Barrier(2)
    call_lock = threading.Lock()
    call_count = 0

    def synchronize_initial_reads(*args, **kwargs):
        nonlocal call_count
        found = original_find(*args, **kwargs)
        if found is None:
            with call_lock:
                call_count += 1
                synchronize = call_count <= 2
            if synchronize:
                first_reads.wait(timeout=5)
        return found

    monkeypatch.setattr(
        reconciliation_service, "_find_external_transaction", synchronize_initial_reads
    )
    first, second = sessions(), sessions()
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    create_external_transaction,
                    db,
                    owner_id,
                    _request("concurrent-evidence"),
                )
                for db in (first, second)
            ]
            results = [future.result(timeout=10) for future in futures]
    finally:
        first.close()
        second.close()

    verifier = sessions()
    try:
        count = (
            verifier.query(ExternalTransaction)
            .filter(
                ExternalTransaction.owner_id == owner_id,
                ExternalTransaction.provider == "stripe",
                ExternalTransaction.external_id == "concurrent-evidence",
            )
            .count()
        )
        events = (
            verifier.query(AuditEvent)
            .filter(
                AuditEvent.actor_user_id == owner_id,
                AuditEvent.action == AuditAction.EXTERNAL_TRANSACTION_INGEST,
            )
            .order_by(AuditEvent.id)
            .all()
        )
    finally:
        verifier.close()

    assert count == 1
    assert {result.external_transaction.id for result in results} == {
        results[0].external_transaction.id
    }
    assert sorted(result.replayed for result in results) == [False, True]
    assert [(event.outcome, event.details) for event in events] == [
        (AuditOutcome.SUCCESS, {}),
        (AuditOutcome.SUCCESS, {"replayed": True}),
    ]


def test_postgresql_listing_is_received_time_then_id_descending(sessions) -> None:
    db = sessions()
    try:
        owner = user(db, 73)
        older = create_external_transaction(db, owner.id, _request("older"))
        same_time_first = create_external_transaction(db, owner.id, _request("same-a"))
        same_time_second = create_external_transaction(db, owner.id, _request("same-b"))
        db.execute(
            update(ExternalTransaction)
            .where(ExternalTransaction.id == older.external_transaction.id)
            .values(received_at=datetime(2026, 9, 10, 10, 0, tzinfo=UTC))
        )
        db.execute(
            update(ExternalTransaction)
            .where(
                ExternalTransaction.id.in_(
                    [
                        same_time_first.external_transaction.id,
                        same_time_second.external_transaction.id,
                    ]
                )
            )
            .values(received_at=datetime(2026, 9, 10, 11, 0, tzinfo=UTC))
        )
        db.commit()
        listed = list_external_transactions(
            db, owner.id, ExternalTransactionListQuery(limit=20)
        )
    finally:
        db.close()

    assert [item.id for item in listed] == [
        same_time_second.external_transaction.id,
        same_time_first.external_transaction.id,
        older.external_transaction.id,
    ]


def test_two_postgresql_sessions_replay_one_same_key_reconciliation(
    sessions, monkeypatch
) -> None:
    setup = sessions()
    try:
        owner = user(setup, 74)
        payment = Payment(
            owner_id=owner.id,
            idempotency_key="reconciliation-payment",
            request_fingerprint="f" * 64,
            amount="12.50",
            currency=Currency.ARS,
            provider=PaymentProvider.STRIPE,
            status=PaymentStatus.COMPLETED,
            recipient_name="Ada Lovelace",
            recipient_account_type=RecipientAccountType.BANK_ACCOUNT,
            recipient_reference="CBU-123",
            provider_payment_id="payment-race",
        )
        setup.add(payment)
        setup.commit()
        evidence = create_external_transaction(
            setup,
            owner.id,
            _request("reconciliation-race", provider_payment_id="payment-race"),
        )
        owner_id = owner.id
        external_id = evidence.external_transaction.id
    finally:
        setup.close()

    original_get = reconciliation_service.get_external_transaction
    initial_reads = threading.Barrier(2)

    def synchronize_initial_reads(*args, **kwargs):
        external = original_get(*args, **kwargs)
        initial_reads.wait(timeout=5)
        return external

    monkeypatch.setattr(
        reconciliation_service, "get_external_transaction", synchronize_initial_reads
    )
    first, second = sessions(), sessions()
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    create_reconciliation,
                    db,
                    owner_id,
                    external_id,
                    "same-reconciliation-key",
                )
                for db in (first, second)
            ]
            results = [future.result(timeout=10) for future in futures]
    finally:
        first.close()
        second.close()

    verifier = sessions()
    try:
        count = (
            verifier.query(Reconciliation)
            .filter(
                Reconciliation.owner_id == owner_id,
                Reconciliation.idempotency_key == "same-reconciliation-key",
            )
            .count()
        )
        events = (
            verifier.query(AuditEvent)
            .filter(
                AuditEvent.actor_user_id == owner_id,
                AuditEvent.action == AuditAction.RECONCILIATION_EXECUTE,
            )
            .order_by(AuditEvent.id)
            .all()
        )
    finally:
        verifier.close()

    assert count == 1
    assert {result.reconciliation.id for result in results} == {
        results[0].reconciliation.id
    }
    assert sorted(result.replayed for result in results) == [False, True]
    assert [(event.outcome, event.details) for event in events] == [
        (AuditOutcome.SUCCESS, {"result": "matched"}),
        (AuditOutcome.SUCCESS, {"replayed": True}),
    ]


def test_reconciliation_postgresql_runtime_proves_snapshots_queries_and_isolation(
    sessions,
) -> None:
    db = sessions()
    app = FastAPI()
    app.include_router(reconciliation_router.router)
    app.include_router(reconciliation_router.reconciliations_router)
    try:
        owner = user(db, 75)
        foreign_owner = user(db, 76)
        payments = [
            Payment(
                owner_id=owner.id,
                idempotency_key=f"payment-{name}",
                request_fingerprint="f" * 64,
                amount="12.50",
                currency=currency,
                provider=PaymentProvider.STRIPE,
                status=PaymentStatus.COMPLETED,
                recipient_name="Ada Lovelace",
                recipient_account_type=RecipientAccountType.BANK_ACCOUNT,
                recipient_reference=f"CBU-{name}",
                provider_payment_id=f"payment-{name}",
            )
            for name, currency in (("match", Currency.ARS), ("currency", Currency.USD))
        ]
        db.add_all(payments)
        db.commit()
        matched_external = create_external_transaction(
            db,
            owner.id,
            _request("match", provider_payment_id="payment-match"),
        )
        currency_external = create_external_transaction(
            db,
            owner.id,
            _request("currency", provider_payment_id="payment-currency"),
        )
        unmatched_external = create_external_transaction(
            db,
            owner.id,
            _request("unmatched", provider_payment_id="payment-unmatched"),
        )
        foreign_external = create_external_transaction(
            db,
            foreign_owner.id,
            _request("foreign", provider_payment_id="payment-foreign"),
        )
        matched = create_reconciliation(
            db, owner.id, matched_external.external_transaction.id, "match-key"
        )
        currency = create_reconciliation(
            db, owner.id, currency_external.external_transaction.id, "currency-key"
        )
        unmatched = create_reconciliation(
            db, owner.id, unmatched_external.external_transaction.id, "unmatched-key"
        )
        foreign = create_reconciliation(
            db,
            foreign_owner.id,
            foreign_external.external_transaction.id,
            "foreign-key",
        )
        db.execute(
            update(Reconciliation)
            .where(
                Reconciliation.id.in_(
                    [
                        matched.reconciliation.id,
                        currency.reconciliation.id,
                        unmatched.reconciliation.id,
                    ]
                )
            )
            .values(reconciled_at=datetime(2026, 9, 10, 18, 0, tzinfo=UTC))
        )
        db.commit()
        for value in (matched, currency, unmatched, foreign):
            db.refresh(value.reconciliation)
            db.expunge(value.reconciliation)
        reconciliation_event_details = [
            event.details
            for event in (
                db.query(AuditEvent)
                .filter(AuditEvent.actor_user_id == owner.id)
                .filter(AuditEvent.action == AuditAction.RECONCILIATION_EXECUTE)
                .order_by(AuditEvent.id)
                .all()
            )
        ]

        app.dependency_overrides[get_current_user] = lambda: owner
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            listed = client.get("/reconciliations?limit=20")
            filtered = client.get("/reconciliations?result=mismatched&limit=1")
            detail = client.get(f"/reconciliations/{matched.reconciliation.id}")
            foreign_reconcile = client.post(
                f"/external-transactions/{foreign_external.external_transaction.id}/reconcile",
                headers={"Idempotency-Key": "foreign-attempt"},
            )
            foreign_detail = client.get(f"/reconciliations/{foreign.reconciliation.id}")
    finally:
        app.dependency_overrides.clear()
        db.close()

    assert (matched.reconciliation.result, currency.reconciliation.result) == (
        "matched",
        "mismatched",
    )
    assert (
        matched.reconciliation.amount_matches,
        matched.reconciliation.currency_matches,
        matched.reconciliation.status_matches,
    ) == (True, True, True)
    assert (
        currency.reconciliation.amount_matches,
        currency.reconciliation.currency_matches,
        currency.reconciliation.status_matches,
    ) == (True, False, True)
    assert (
        unmatched.reconciliation.payment_id,
        unmatched.reconciliation.local_amount,
        unmatched.reconciliation.local_currency,
        unmatched.reconciliation.local_status,
        unmatched.reconciliation.amount_matches,
        unmatched.reconciliation.currency_matches,
        unmatched.reconciliation.status_matches,
    ) == (None, None, None, None, None, None, None)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [
        unmatched.reconciliation.id,
        currency.reconciliation.id,
        matched.reconciliation.id,
    ]
    assert filtered.json()[0]["id"] == currency.reconciliation.id
    assert detail.json()["reconciled_at"] == "2026-09-10T18:00:00Z"
    assert (foreign_reconcile.status_code, foreign_detail.status_code) == (404, 404)
    assert reconciliation_event_details == [
        {"result": "matched"},
        {"result": "mismatched"},
        {"result": "unmatched"},
    ]
