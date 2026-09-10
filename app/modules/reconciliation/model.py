from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeAlias

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.payments.enums import Currency, PaymentProvider, PaymentStatus
from app.modules.reconciliation.enums import ReconciliationResult

ReconciliationEnum: TypeAlias = (
    type[Currency]
    | type[PaymentProvider]
    | type[PaymentStatus]
    | type[ReconciliationResult]
)


def _enum_values(enum_class: ReconciliationEnum) -> Sequence[str]:
    return [member.value for member in enum_class]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ExternalTransaction(Base):
    __tablename__ = "external_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[PaymentProvider] = mapped_column(
        ENUM(
            PaymentProvider,
            name="payment_provider",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_payment_id: Mapped[str] = mapped_column(String(255), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[Currency] = mapped_column(
        ENUM(
            Currency,
            name="payment_currency",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    status: Mapped[PaymentStatus] = mapped_column(
        ENUM(
            PaymentStatus,
            name="payment_status",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_external_transactions_amount_positive"),
        CheckConstraint(
            "status IN ('completed', 'rejected', 'failed', 'cancelled')",
            name="ck_external_transactions_status_terminal",
        ),
        UniqueConstraint(
            "owner_id",
            "provider",
            "external_id",
            name="uq_external_transactions_owner_provider_external_id",
        ),
        Index(
            "ix_external_transactions_owner_received_at_id",
            "owner_id",
            "received_at",
            "id",
        ),
    )


class Reconciliation(Base):
    __tablename__ = "reconciliations"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    external_transaction_id: Mapped[int] = mapped_column(
        ForeignKey("external_transactions.id", ondelete="RESTRICT"), nullable=False
    )
    payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("payments.id", ondelete="RESTRICT")
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    external_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    external_currency: Mapped[Currency] = mapped_column(
        ENUM(
            Currency,
            name="payment_currency",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    external_status: Mapped[PaymentStatus] = mapped_column(
        ENUM(
            PaymentStatus,
            name="payment_status",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    local_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    local_currency: Mapped[Currency | None] = mapped_column(
        ENUM(
            Currency,
            name="payment_currency",
            values_callable=_enum_values,
            create_type=False,
        )
    )
    local_status: Mapped[PaymentStatus | None] = mapped_column(
        ENUM(
            PaymentStatus,
            name="payment_status",
            values_callable=_enum_values,
            create_type=False,
        )
    )
    result: Mapped[ReconciliationResult] = mapped_column(
        ENUM(
            ReconciliationResult,
            name="reconciliation_result",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    amount_matches: Mapped[bool | None] = mapped_column(Boolean)
    currency_matches: Mapped[bool | None] = mapped_column(Boolean)
    status_matches: Mapped[bool | None] = mapped_column(Boolean)
    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utc_now, nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "external_amount > 0",
            name="ck_reconciliations_external_amount_positive",
        ),
        CheckConstraint(
            "(result = 'unmatched' AND payment_id IS NULL AND local_amount IS NULL AND "
            "local_currency IS NULL AND local_status IS NULL AND "
            "amount_matches IS NULL AND currency_matches IS NULL AND "
            "status_matches IS NULL) OR result != 'unmatched'",
            name="ck_reconciliations_unmatched_nulls",
        ),
        CheckConstraint(
            "(result IN ('matched', 'mismatched') AND payment_id IS NOT NULL AND "
            "local_amount IS NOT NULL AND local_currency IS NOT NULL AND "
            "local_status IS NOT NULL AND "
            "amount_matches IS NOT NULL AND currency_matches IS NOT NULL AND "
            "status_matches IS NOT NULL) OR result NOT IN ('matched', 'mismatched')",
            name="ck_reconciliations_local_snapshot_required",
        ),
        CheckConstraint(
            "result != 'matched' OR "
            "(amount_matches IS TRUE AND currency_matches IS TRUE AND "
            "status_matches IS TRUE)",
            name="ck_reconciliations_matched_flags",
        ),
        CheckConstraint(
            "result != 'mismatched' OR "
            "(amount_matches IS FALSE OR currency_matches IS FALSE OR "
            "status_matches IS FALSE)",
            name="ck_reconciliations_mismatched_flags",
        ),
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_reconciliations_owner_idempotency_key",
        ),
        Index(
            "ix_reconciliations_owner_reconciled_at_id",
            "owner_id",
            "reconciled_at",
            "id",
        ),
        Index(
            "ix_reconciliations_owner_result_reconciled_at_id",
            "owner_id",
            "result",
            "reconciled_at",
            "id",
        ),
    )
