from decimal import Decimal

from sqlalchemy import CheckConstraint, Enum, Numeric, UniqueConstraint

from app.core.database import Base
from app.modules.payments.enums import (
    Currency,
    PaymentProvider,
    PaymentStatus,
    RecipientAccountType,
)
from app.modules.payments.model import Payment


def test_payment_model_persists_financial_instruction_snapshot() -> None:
    table = Payment.__table__

    assert isinstance(table.c.amount.type, Numeric)
    assert table.c.amount.type.precision == 18
    assert table.c.amount.type.scale == 2
    assert table.c.amount.nullable is False
    assert table.c.recipient_name.nullable is False
    assert table.c.recipient_account_type.nullable is False
    assert table.c.recipient_reference.nullable is False
    assert table.c.recipient_description.nullable is True
    assert table.c.provider_payment_id.nullable is True
    assert table.c.failure_code.nullable is True
    assert table.c.failure_message.nullable is True
    assert table.c.processed_at.nullable is True
    assert {"created_at", "updated_at"} <= set(table.c.keys())


def test_payment_model_uses_closed_enum_values_and_financial_constraints() -> None:
    table = Payment.__table__

    assert isinstance(table.c.currency.type, Enum)
    assert table.c.currency.type.enums == ["ARS", "USD"]
    assert table.c.provider.type.enums == ["mercado_pago", "uala", "stripe"]
    assert table.c.status.type.enums == [
        "pending",
        "processing",
        "completed",
        "rejected",
        "failed",
        "cancelled",
    ]
    assert table.c.recipient_account_type.type.enums == [
        "bank_account",
        "virtual_wallet",
        "provider_account",
    ]

    checks = {
        constraint.sqltext.text
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "amount > 0" in checks

    unique_constraints = [
        constraint
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    assert any(
        tuple(column.name for column in constraint.columns)
        == ("owner_id", "idempotency_key")
        for constraint in unique_constraints
    )


def test_payment_model_exposes_owner_scoped_indexes_and_metadata() -> None:
    table = Payment.__table__
    indexes = {
        (index.name, tuple(column.name for column in index.columns))
        for index in table.indexes
    }

    assert ("ix_payments_owner_created_at", ("owner_id", "created_at")) in indexes
    assert ("ix_payments_owner_status", ("owner_id", "status")) in indexes
    assert ("ix_payments_owner_provider", ("owner_id", "provider")) in indexes
    assert ("ix_payments_owner_currency", ("owner_id", "currency")) in indexes
    assert Base.metadata.tables["payments"] is table

    payment = Payment(
        owner_id=5,
        idempotency_key="payment-001",
        request_fingerprint="f" * 64,
        amount=Decimal("42.50"),
        currency=Currency.ARS,
        provider=PaymentProvider.MERCADO_PAGO,
        status=PaymentStatus.PENDING,
        recipient_name="Ada Lovelace",
        recipient_account_type=RecipientAccountType.BANK_ACCOUNT,
        recipient_reference="CBU-123",
    )

    assert payment.amount == Decimal("42.50")
    assert payment.status is PaymentStatus.PENDING
