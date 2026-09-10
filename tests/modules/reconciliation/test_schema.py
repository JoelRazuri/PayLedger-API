from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.payments.enums import Currency, PaymentProvider, PaymentStatus
from app.modules.reconciliation.schema import (
    ExternalTransactionCreate,
    ExternalTransactionListQuery,
)


def payload(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "provider": "stripe",
        "external_id": "  event-1  ",
        "provider_payment_id": "  payment-1  ",
        "amount": "12.50",
        "currency": "ARS",
        "status": "completed",
        "occurred_at": "2026-09-10T12:00:00.123456-03:00",
    }
    value.update(overrides)
    return value


def test_external_transaction_create_normalizes_identifiers_and_utc_time() -> None:
    request = ExternalTransactionCreate.model_validate(payload())

    assert request.provider is PaymentProvider.STRIPE
    assert request.currency is Currency.ARS
    assert request.status is PaymentStatus.COMPLETED
    assert request.amount == Decimal("12.50")
    assert request.external_id == "event-1"
    assert request.provider_payment_id == "payment-1"
    assert request.occurred_at == datetime(2026, 9, 10, 15, 0, 0, 123456, tzinfo=UTC)


@pytest.mark.parametrize(
    "invalid",
    [
        payload(status="pending"),
        payload(status="processing"),
        payload(occurred_at="2026-09-10T12:00:00"),
        payload(external_id="   "),
        payload(provider_payment_id="   "),
        payload(amount="0"),
        payload(currency="EUR"),
    ],
)
def test_external_transaction_create_rejects_non_terminal_or_invalid_evidence(
    invalid: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        ExternalTransactionCreate.model_validate(invalid)


def test_external_transaction_list_query_enforces_page_bounds() -> None:
    assert ExternalTransactionListQuery().model_dump() == {"limit": 20, "offset": 0}

    with pytest.raises(ValidationError):
        ExternalTransactionListQuery(limit=101)
