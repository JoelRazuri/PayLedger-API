import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.reconciliation import router as reconciliation_router
from app.modules.reconciliation import service as reconciliation_service
from app.modules.reconciliation.model import ExternalTransaction
from app.modules.reconciliation.schema import (
    ExternalTransactionCreate,
    ExternalTransactionListQuery,
)
from app.modules.reconciliation.service import (
    create_external_transaction,
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
    finally:
        verifier.close()

    assert count == 1
    assert {result.external_transaction.id for result in results} == {
        results[0].external_transaction.id
    }
    assert sorted(result.replayed for result in results) == [False, True]


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
