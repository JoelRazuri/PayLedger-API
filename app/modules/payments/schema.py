from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.modules.payments.enums import (
    Currency,
    PaymentProcessScenario,
    PaymentProvider,
    PaymentStatus,
    RecipientAccountType,
)


class RecipientInput(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    account_type: RecipientAccountType
    reference: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)

    @field_validator("name", "reference", "description", mode="before")
    @classmethod
    def strip_snapshot_values(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class PaymentCreate(BaseModel):
    amount: Decimal = Field(gt=Decimal("0"), max_digits=18, decimal_places=2)
    currency: Currency
    provider: PaymentProvider
    recipient: RecipientInput


class PaymentProcessRequest(BaseModel):
    simulation_scenario: PaymentProcessScenario


class PaymentListQuery(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    status: PaymentStatus | None = None
    provider: PaymentProvider | None = None
    currency: Currency | None = None


class PaymentRecipientResponse(BaseModel):
    name: str
    account_type: RecipientAccountType
    reference: str
    description: str | None


class PaymentResponse(BaseModel):
    id: int
    amount: Decimal
    currency: Currency
    provider: PaymentProvider
    status: PaymentStatus
    recipient_name: str
    recipient_account_type: RecipientAccountType
    recipient_reference: str
    recipient_description: str | None
    provider_payment_id: str | None
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}
