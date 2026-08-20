from enum import StrEnum


class LedgerEventType(StrEnum):
    PAYMENT_COMPLETED = "payment_completed"


class LedgerEntrySide(StrEnum):
    DEBIT = "debit"
    CREDIT = "credit"


class LedgerAccount(StrEnum):
    PAYMENT_EXPENSE = "PAYMENT_EXPENSE"
    EXTERNAL_FUNDS = "EXTERNAL_FUNDS"
