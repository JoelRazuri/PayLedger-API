from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.ledger.enums import LedgerAccount, LedgerEntrySide, LedgerEventType
from app.modules.payments.enums import Currency


class LedgerListQuery(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    currency: Currency | None = None
    account: LedgerAccount | None = None


class LedgerEntryResponse(BaseModel):
    id: int
    side: LedgerEntrySide
    account: LedgerAccount
    amount: Decimal
    currency: Currency

    model_config = {"from_attributes": True}


class JournalResponse(BaseModel):
    id: int
    payment_id: int
    event_type: LedgerEventType
    amount: Decimal
    currency: Currency
    occurred_at: datetime
    created_at: datetime
    entries: list[LedgerEntryResponse]

    model_config = {"from_attributes": True}
