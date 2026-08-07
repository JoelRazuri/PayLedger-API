from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.payments import router as payments_router
from app.modules.payments.enums import (
    Currency,
    PaymentProvider,
    PaymentStatus,
    RecipientAccountType,
)
from app.modules.payments.exceptions import (
    PaymentIdempotencyConflictError,
    PaymentNotFoundError,
    PaymentStateConflictError,
)
from app.modules.payments.model import Payment
from app.modules.payments.service import PaymentCreation
from app.modules.users.model import User

client = TestClient(app)


def payment(status: PaymentStatus = PaymentStatus.PENDING) -> Payment:
    timestamp = datetime(2026, 8, 7, 12, 0, tzinfo=UTC)
    return Payment(
        id=4,
        owner_id=7,
        idempotency_key="key-1",
        request_fingerprint="f" * 64,
        amount=Decimal("12.50"),
        currency=Currency.ARS,
        provider=PaymentProvider.MERCADO_PAGO,
        status=status,
        recipient_name="Ada Lovelace",
        recipient_account_type=RecipientAccountType.BANK_ACCOUNT,
        recipient_reference="CBU-123",
        created_at=timestamp,
        updated_at=timestamp,
    )


@pytest.fixture(autouse=True)
def override_dependencies() -> MagicMock:
    db = MagicMock()
    app.dependency_overrides[get_current_user] = lambda: User(id=7)
    app.dependency_overrides[get_db] = lambda: db
    yield db
    app.dependency_overrides.clear()


def payload(amount: str = "12.50") -> dict[str, object]:
    return {
        "amount": amount,
        "currency": "ARS",
        "provider": "mercado_pago",
        "recipient": {
            "name": "Ada Lovelace",
            "account_type": "bank_account",
            "reference": "CBU-123",
        },
    }


def test_payments_require_authentication() -> None:
    app.dependency_overrides.pop(get_current_user)

    response = client.get("/payments")

    assert response.status_code == 401


def test_create_returns_201_then_200_for_replay(monkeypatch) -> None:
    create = MagicMock(
        side_effect=[
            PaymentCreation(payment(), False),
            PaymentCreation(payment(), True),
        ]
    )
    monkeypatch.setattr(payments_router, "create_payment", create)

    first = client.post(
        "/payments", headers={"Idempotency-Key": "key-1"}, json=payload()
    )
    replay = client.post(
        "/payments", headers={"Idempotency-Key": "key-1"}, json=payload()
    )

    assert (first.status_code, replay.status_code) == (201, 200)
    assert first.json()["status"] == "pending"
    assert create.call_args.args[1] == 7


def test_create_maps_conflict_and_invalid_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        payments_router,
        "create_payment",
        MagicMock(side_effect=PaymentIdempotencyConflictError),
    )

    conflict = client.post(
        "/payments", headers={"Idempotency-Key": "key-1"}, json=payload()
    )
    invalid = client.post(
        "/payments", headers={"Idempotency-Key": "key-2"}, json=payload("0")
    )

    assert conflict.json() == {
        "detail": "La clave de idempotencia ya fue utilizada con otra solicitud"
    }
    assert conflict.status_code == 409
    assert invalid.json() == {"detail": "Solicitud inv\u00e1lida"}
    assert invalid.status_code == 422


def test_list_and_get_return_only_service_owned_payments(monkeypatch) -> None:
    monkeypatch.setattr(
        payments_router, "list_payments", MagicMock(return_value=[payment()])
    )
    monkeypatch.setattr(
        payments_router, "get_payment", MagicMock(return_value=payment())
    )

    listed = client.get("/payments?limit=1&status=pending")
    fetched = client.get("/payments/4")

    assert listed.json()[0]["id"] == 4
    assert fetched.json()["recipient_reference"] == "CBU-123"


@pytest.mark.parametrize(
    ("method", "path", "exception", "status_code", "detail"),
    [
        ("get", "/payments/4", PaymentNotFoundError, 404, "Pago no encontrado"),
        (
            "post",
            "/payments/4/process",
            PaymentStateConflictError,
            409,
            "El pago no está disponible para esta acción",
        ),
        ("post", "/payments/4/cancel", PaymentNotFoundError, 404, "Pago no encontrado"),
    ],
)
def test_actions_map_owner_safe_errors_to_spanish_http(
    monkeypatch,
    method: str,
    path: str,
    exception: type[Exception],
    status_code: int,
    detail: str,
) -> None:
    target = (
        "get_payment"
        if method == "get"
        else "process_payment"
        if "process" in path
        else "cancel_payment"
    )
    monkeypatch.setattr(payments_router, target, MagicMock(side_effect=exception))

    request = getattr(client, method)
    if "process" in path:
        response = request(path, json={"simulation_scenario": "success"})
    else:
        response = request(path)

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
