from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.payments.enums import (
    Currency,
    PaymentProvider,
    RecipientAccountType,
)
from app.modules.payments.schema import PaymentCreate, RecipientInput


def payment_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "amount": "1200.50",
        "currency": "ARS",
        "provider": "mercado_pago",
        "recipient": {
            "name": "  Ada Lovelace  ",
            "account_type": "bank_account",
            "reference": "  CBU-123  ",
            "description": "  August payment  ",
        },
    }
    payload.update(overrides)
    return payload


def test_payment_create_normalizes_supported_exact_money_and_snapshot() -> None:
    payment = PaymentCreate.model_validate(payment_payload())

    assert payment.amount == Decimal("1200.50")
    assert payment.currency is Currency.ARS
    assert payment.provider is PaymentProvider.MERCADO_PAGO
    assert payment.recipient == RecipientInput(
        name="Ada Lovelace",
        account_type=RecipientAccountType.BANK_ACCOUNT,
        reference="CBU-123",
        description="August payment",
    )


@pytest.mark.parametrize(
    "payload",
    [
        payment_payload(amount="0"),
        payment_payload(amount="-0.01"),
        payment_payload(amount="1.001"),
        payment_payload(amount="12345678901234567.89"),
        payment_payload(currency="EUR"),
        payment_payload(provider="cash"),
        payment_payload(
            recipient={
                "name": "",
                "account_type": "bank_account",
                "reference": "x",
            }
        ),
        payment_payload(
            recipient={"name": "Ada", "account_type": "cash", "reference": "x"}
        ),
        payment_payload(
            recipient={
                "name": "Ada",
                "account_type": "bank_account",
                "reference": "",
            }
        ),
    ],
)
def test_payment_create_rejects_invalid_financial_and_snapshot_values(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        PaymentCreate.model_validate(payload)
