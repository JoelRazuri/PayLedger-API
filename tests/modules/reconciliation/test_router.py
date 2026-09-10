from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.payments.enums import Currency, PaymentProvider, PaymentStatus
from app.modules.reconciliation import router as reconciliation_router
from app.modules.reconciliation.exceptions import (
    ExternalTransactionConflictError,
    ExternalTransactionNotFoundError,
    ReconciliationConflictError,
    ReconciliationNotFoundError,
)
from app.modules.reconciliation.model import ExternalTransaction, Reconciliation
from app.modules.reconciliation.service import (
    ExternalTransactionCreation,
    ReconciliationCreation,
)
from app.modules.users.model import User


def external_transaction() -> ExternalTransaction:
    return ExternalTransaction(
        id=4,
        owner_id=7,
        provider=PaymentProvider.STRIPE,
        external_id="event-1",
        provider_payment_id="payment-1",
        request_fingerprint="f" * 64,
        amount=Decimal("12.50"),
        currency=Currency.ARS,
        status=PaymentStatus.COMPLETED,
        occurred_at=datetime(2026, 9, 10, 15, 0, tzinfo=UTC),
        received_at=datetime(2026, 9, 10, 15, 1, tzinfo=UTC),
    )


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(reconciliation_router.router)
    app.dependency_overrides[get_current_user] = lambda: User(id=7)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "provider": "stripe",
        "external_id": "event-1",
        "provider_payment_id": "payment-1",
        "amount": "12.50",
        "currency": "ARS",
        "status": "completed",
        "occurred_at": "2026-09-10T12:00:00-03:00",
    }
    value.update(overrides)
    return value


@pytest.mark.parametrize(
    ("method", "path", "body", "headers"),
    [
        ("post", "/external-transactions", payload(), {}),
        ("post", "/external-transactions", payload(), {"Authorization": "Bearer bad"}),
        ("get", "/external-transactions", None, {}),
        ("get", "/external-transactions", None, {"Authorization": "Bearer bad"}),
        ("get", "/external-transactions/4", None, {}),
        ("get", "/external-transactions/4", None, {"Authorization": "Bearer bad"}),
    ],
)
def test_evidence_routes_require_jwt(
    method: str,
    path: str,
    body: dict | None,
    headers: dict[str, str],
) -> None:
    app = FastAPI()
    app.include_router(reconciliation_router.router)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    try:
        with TestClient(app) as client:
            response = (
                client.post(path, json=body, headers=headers)
                if method == "post"
                else client.get(path, headers=headers)
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_create_evidence_returns_201_then_200_with_utc_response(
    client, monkeypatch
) -> None:
    create = MagicMock(
        side_effect=[
            ExternalTransactionCreation(external_transaction(), replayed=False),
            ExternalTransactionCreation(external_transaction(), replayed=True),
        ]
    )
    monkeypatch.setattr(reconciliation_router, "create_external_transaction", create)

    first = client.post("/external-transactions", json=payload())
    replay = client.post("/external-transactions", json=payload())

    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["occurred_at"] == "2026-09-10T15:00:00Z"
    assert first.json()["received_at"] == "2026-09-10T15:01:00Z"
    assert create.call_args.args[1] == 7


def test_evidence_routes_map_invalid_conflict_and_not_found_to_spanish_http(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        reconciliation_router,
        "create_external_transaction",
        MagicMock(side_effect=ExternalTransactionConflictError),
    )
    monkeypatch.setattr(
        reconciliation_router,
        "get_external_transaction",
        MagicMock(side_effect=ExternalTransactionNotFoundError),
    )

    conflict = client.post("/external-transactions", json=payload())
    invalid = client.post("/external-transactions", json=payload(status="pending"))
    missing = client.get("/external-transactions/99")

    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": "La transacción externa ya existe con datos diferentes"
    }
    assert invalid.status_code == 422
    assert invalid.json() == {"detail": "Solicitud inválida"}
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Transacción externa no encontrada"}


def test_list_and_mutation_methods_preserve_owner_scoped_evidence(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        reconciliation_router,
        "list_external_transactions",
        MagicMock(return_value=[external_transaction()]),
    )

    listed = client.get("/external-transactions?limit=1")
    methods = [
        response
        for path in ("/external-transactions", "/external-transactions/4")
        for response in (
            client.patch(path, json={"amount": "99"}),
            client.put(path, json={"amount": "99"}),
            client.delete(path),
        )
    ]

    assert listed.json()[0]["id"] == 4
    assert [response.status_code for response in methods] == [405] * 6


def test_create_evidence_rejects_timezone_naive_occurrence_at(client) -> None:
    response = client.post(
        "/external-transactions",
        json=payload(occurred_at="2026-09-10T15:00:00"),
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Solicitud inválida"}


def reconciliation(
    *,
    identifier: int = 11,
    external_transaction_id: int = 4,
    payment_id: int | None = 9,
    result: str = "matched",
) -> Reconciliation:
    return Reconciliation(
        id=identifier,
        owner_id=7,
        external_transaction_id=external_transaction_id,
        payment_id=payment_id,
        idempotency_key=f"key-{identifier}",
        external_amount=Decimal("12.50"),
        external_currency=Currency.ARS,
        external_status=PaymentStatus.COMPLETED,
        local_amount=Decimal("12.50") if payment_id is not None else None,
        local_currency=Currency.ARS if payment_id is not None else None,
        local_status=PaymentStatus.COMPLETED if payment_id is not None else None,
        result=result,
        amount_matches=True if payment_id is not None else None,
        currency_matches=True if payment_id is not None else None,
        status_matches=True if payment_id is not None else None,
        reconciled_at=datetime(2026, 9, 10, 15, 2, tzinfo=UTC),
    )


@pytest.fixture
def reconciliation_client() -> TestClient:
    app = FastAPI()
    app.include_router(reconciliation_router.router)
    app.include_router(reconciliation_router.reconciliations_router)
    app.dependency_overrides[get_current_user] = lambda: User(id=7)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_reconcile_route_requires_key_and_maps_foreign_or_unknown_to_404(
    reconciliation_client, monkeypatch
) -> None:
    monkeypatch.setattr(
        reconciliation_router,
        "create_reconciliation",
        MagicMock(side_effect=ExternalTransactionNotFoundError),
    )
    monkeypatch.setattr(
        reconciliation_router,
        "get_reconciliation",
        MagicMock(side_effect=ReconciliationNotFoundError),
    )

    missing_key = reconciliation_client.post("/external-transactions/4/reconcile")
    foreign = reconciliation_client.post(
        "/external-transactions/99/reconcile", headers={"Idempotency-Key": "key"}
    )
    unknown = reconciliation_client.get("/reconciliations/99")

    assert (missing_key.status_code, foreign.status_code, unknown.status_code) == (
        422,
        404,
        404,
    )


def test_reconcile_route_replays_conflicts_and_appends_new_attempts(
    reconciliation_client, monkeypatch
) -> None:
    first = reconciliation(identifier=11)
    replay = reconciliation(identifier=11)
    rerun = reconciliation(identifier=12)
    create = MagicMock(
        side_effect=[
            ReconciliationCreation(first, replayed=False),
            ReconciliationCreation(replay, replayed=True),
            ReconciliationConflictError,
            ReconciliationCreation(rerun, replayed=False),
        ]
    )
    monkeypatch.setattr(reconciliation_router, "create_reconciliation", create)

    created = reconciliation_client.post(
        "/external-transactions/4/reconcile", headers={"Idempotency-Key": "first"}
    )
    same_key = reconciliation_client.post(
        "/external-transactions/4/reconcile", headers={"Idempotency-Key": "first"}
    )
    reused_elsewhere = reconciliation_client.post(
        "/external-transactions/5/reconcile", headers={"Idempotency-Key": "first"}
    )
    new_key = reconciliation_client.post(
        "/external-transactions/4/reconcile", headers={"Idempotency-Key": "second"}
    )

    statuses = (
        created.status_code,
        same_key.status_code,
        reused_elsewhere.status_code,
    )
    assert statuses == (
        200,
        200,
        409,
    )
    assert (created.json()["id"], same_key.json()["id"], new_key.json()["id"]) == (
        11,
        11,
        12,
    )
    assert create.call_args_list[0].args[1:] == (7, 4, "first")


def test_reconciliation_query_routes_filter_page_and_are_immutable(
    reconciliation_client, monkeypatch
) -> None:
    listed = reconciliation(identifier=11)
    monkeypatch.setattr(
        reconciliation_router, "list_reconciliations", MagicMock(return_value=[listed])
    )

    response = reconciliation_client.get("/reconciliations?result=matched&limit=1")
    invalid = reconciliation_client.get("/reconciliations?result=invalid")
    invalid_limit = reconciliation_client.get("/reconciliations?limit=101")
    invalid_offset = reconciliation_client.get("/reconciliations?offset=-1")
    methods = [
        response
        for path in ("/reconciliations", "/reconciliations/11")
        for response in (
            reconciliation_client.patch(path, json={"result": "mismatched"}),
            reconciliation_client.put(path, json={"result": "mismatched"}),
            reconciliation_client.delete(path),
        )
    ]

    assert response.status_code == 200
    assert response.json()[0]["reconciled_at"] == "2026-09-10T15:02:00Z"
    invalid_statuses = (
        invalid.status_code,
        invalid_limit.status_code,
        invalid_offset.status_code,
    )
    assert invalid_statuses == (
        422,
        422,
        422,
    )
    assert [item.status_code for item in methods] == [405] * 6
