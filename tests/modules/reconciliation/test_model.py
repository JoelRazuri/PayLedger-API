from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKeyConstraint,
    Index,
    Numeric,
    UniqueConstraint,
)

from app.core.database import Base
from app.modules.payments.enums import Currency, PaymentProvider, PaymentStatus
from app.modules.reconciliation.enums import ReconciliationResult
from app.modules.reconciliation.model import ExternalTransaction, Reconciliation


def _checks(table) -> dict[str, str]:
    return {
        constraint.name: constraint.sqltext.text
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }


def _foreign_keys(table) -> set[tuple[str, str, str]]:
    return {
        (
            foreign_key.parent.name,
            foreign_key.target_fullname,
            foreign_key.ondelete or "",
        )
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
        for foreign_key in constraint.elements
    }


def _indexes(table) -> set[tuple[str, tuple[str, ...]]]:
    return {
        (index.name, tuple(column.name for column in index.columns))
        for index in table.indexes
        if isinstance(index, Index)
    }


def test_external_transaction_model_preserves_immutable_provider_evidence() -> None:
    table = ExternalTransaction.__table__

    assert isinstance(table.c.amount.type, Numeric)
    assert table.c.amount.type.precision == 18
    assert table.c.amount.type.scale == 2
    assert table.c.provider.type.enums == [member.value for member in PaymentProvider]
    assert table.c.currency.type.enums == [member.value for member in Currency]
    assert table.c.status.type.enums == [member.value for member in PaymentStatus]
    assert table.c.external_id.type.length == 255
    assert table.c.provider_payment_id.type.length == 255
    assert table.c.request_fingerprint.type.length == 64
    assert table.c.occurred_at.type.timezone is True
    assert table.c.received_at.type.timezone is True

    assert _checks(table) == {
        "ck_external_transactions_amount_positive": "amount > 0",
        "ck_external_transactions_status_terminal": (
            "status IN ('completed', 'rejected', 'failed', 'cancelled')"
        ),
    }
    assert _foreign_keys(table) == {
        ("owner_id", "users.id", "RESTRICT"),
    }
    assert any(
        constraint.name == "uq_external_transactions_owner_provider_external_id"
        and tuple(column.name for column in constraint.columns)
        == ("owner_id", "provider", "external_id")
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    assert _indexes(table) == {
        (
            "ix_external_transactions_owner_received_at_id",
            ("owner_id", "received_at", "id"),
        ),
    }
    assert Base.metadata.tables["external_transactions"] is table


def test_reconciliation_model_requires_consistent_snapshot_result_state() -> None:
    table = Reconciliation.__table__

    assert isinstance(table.c.result.type, Enum)
    assert table.c.result.type.enums == [
        member.value for member in ReconciliationResult
    ]
    assert table.c.external_amount.type.precision == 18
    assert table.c.local_amount.nullable is True
    assert table.c.payment_id.nullable is True
    assert table.c.amount_matches.nullable is True
    assert table.c.reconciled_at.type.timezone is True
    assert table.c.idempotency_key.type.length == 255

    checks = _checks(table)
    assert (
        checks["ck_reconciliations_external_amount_positive"] == "external_amount > 0"
    )
    assert "result = 'unmatched'" in checks["ck_reconciliations_unmatched_nulls"]
    assert "payment_id IS NULL" in checks["ck_reconciliations_unmatched_nulls"]
    assert "amount_matches IS NULL" in checks["ck_reconciliations_unmatched_nulls"]
    assert (
        "result IN ('matched', 'mismatched')"
        in checks["ck_reconciliations_local_snapshot_required"]
    )
    assert (
        "payment_id IS NOT NULL" in checks["ck_reconciliations_local_snapshot_required"]
    )
    assert (
        "local_amount IS NOT NULL"
        in checks["ck_reconciliations_local_snapshot_required"]
    )
    assert (
        "amount_matches IS NOT NULL"
        in checks["ck_reconciliations_local_snapshot_required"]
    )
    assert "amount_matches IS TRUE" in checks["ck_reconciliations_matched_flags"]
    assert "amount_matches IS FALSE" in checks["ck_reconciliations_mismatched_flags"]

    assert _foreign_keys(table) == {
        ("owner_id", "users.id", "RESTRICT"),
        ("external_transaction_id", "external_transactions.id", "RESTRICT"),
        ("payment_id", "payments.id", "RESTRICT"),
    }
    assert any(
        constraint.name == "uq_reconciliations_owner_idempotency_key"
        and tuple(column.name for column in constraint.columns)
        == ("owner_id", "idempotency_key")
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    )
    assert _indexes(table) == {
        (
            "ix_reconciliations_owner_reconciled_at_id",
            ("owner_id", "reconciled_at", "id"),
        ),
        (
            "ix_reconciliations_owner_result_reconciled_at_id",
            ("owner_id", "result", "reconciled_at", "id"),
        ),
    }


def test_reconciliation_result_is_closed_vocabulary() -> None:
    assert [member.value for member in ReconciliationResult] == [
        "matched",
        "mismatched",
        "unmatched",
    ]
    assert ReconciliationResult.MATCHED is ReconciliationResult("matched")
    assert (
        ExternalTransaction(
            owner_id=1,
            provider=PaymentProvider.STRIPE,
            external_id="evt-1",
            provider_payment_id="payment-1",
            request_fingerprint="a" * 64,
            amount=Decimal("12.50"),
            currency=Currency.ARS,
            status=PaymentStatus.COMPLETED,
        ).status
        is PaymentStatus.COMPLETED
    )
