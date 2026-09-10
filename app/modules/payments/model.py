from datetime import UTC, datetime
from decimal import Decimal
from typing import TypeAlias

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.payments.enums import (
    Currency,
    PaymentProvider,
    PaymentStatus,
    RecipientAccountType,
)

PaymentEnum: TypeAlias = (
    type[Currency]
    | type[PaymentProvider]
    | type[PaymentStatus]
    | type[RecipientAccountType]
)


def _enum_values(enum_class: PaymentEnum) -> list[str]:
    return [member.value for member in enum_class]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
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
    provider: Mapped[PaymentProvider] = mapped_column(
        ENUM(
            PaymentProvider,
            name="payment_provider",
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
        default=PaymentStatus.PENDING,
        nullable=False,
    )
    recipient_name: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_account_type: Mapped[RecipientAccountType] = mapped_column(
        ENUM(
            RecipientAccountType,
            name="recipient_account_type",
            values_callable=_enum_values,
            create_type=False,
        ),
        nullable=False,
    )
    recipient_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_description: Mapped[str | None] = mapped_column(String(500))
    provider_payment_id: Mapped[str | None] = mapped_column(String(255))
    failure_code: Mapped[str | None] = mapped_column(String(100))
    failure_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utc_now,
        onupdate=_utc_now,
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount_positive"),
        Index("ix_payments_owner_created_at", "owner_id", "created_at"),
        Index("ix_payments_owner_status", "owner_id", "status"),
        Index("ix_payments_owner_provider", "owner_id", "provider"),
        Index("ix_payments_owner_currency", "owner_id", "currency"),
        Index(
            "uq_payments_owner_provider_provider_payment_id",
            "owner_id",
            "provider",
            "provider_payment_id",
            unique=True,
            postgresql_where=text("provider_payment_id IS NOT NULL"),
        ),
        UniqueConstraint(
            "owner_id",
            "idempotency_key",
            name="uq_payments_owner_idempotency_key",
        ),
    )
