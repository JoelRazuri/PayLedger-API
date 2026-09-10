from datetime import UTC, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.modules.payments.enums import Currency, PaymentProvider, PaymentStatus

_TERMINAL_STATUSES = {
    PaymentStatus.COMPLETED,
    PaymentStatus.REJECTED,
    PaymentStatus.FAILED,
    PaymentStatus.CANCELLED,
}


class ExternalTransactionCreate(BaseModel):
    provider: PaymentProvider
    external_id: str = Field(min_length=1, max_length=255)
    provider_payment_id: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=Decimal("0"), max_digits=18, decimal_places=2)
    currency: Currency
    status: PaymentStatus
    occurred_at: datetime

    @field_validator("external_id", "provider_payment_id", mode="before")
    @classmethod
    def strip_provider_identifiers(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("status")
    @classmethod
    def require_terminal_status(cls, value: PaymentStatus) -> PaymentStatus:
        if value not in _TERMINAL_STATUSES:
            raise ValueError("external transaction status must be terminal")
        return value

    @field_validator("occurred_at")
    @classmethod
    def normalize_occurred_at_to_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        return value.astimezone(UTC)


class ExternalTransactionListQuery(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class ExternalTransactionResponse(BaseModel):
    id: int
    provider: PaymentProvider
    external_id: str
    provider_payment_id: str
    amount: Decimal
    currency: Currency
    status: PaymentStatus
    occurred_at: datetime
    received_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("occurred_at", "received_at")
    @classmethod
    def normalize_response_time_to_utc(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)
