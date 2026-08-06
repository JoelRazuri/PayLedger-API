from enum import StrEnum


class Currency(StrEnum):
    ARS = "ARS"
    USD = "USD"


class PaymentProvider(StrEnum):
    MERCADO_PAGO = "mercado_pago"
    UALA = "uala"
    STRIPE = "stripe"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RecipientAccountType(StrEnum):
    BANK_ACCOUNT = "bank_account"
    VIRTUAL_WALLET = "virtual_wallet"
    PROVIDER_ACCOUNT = "provider_account"


class PaymentProcessScenario(StrEnum):
    SUCCESS = "success"
    BUSINESS_REJECTION = "business_rejection"
    TECHNICAL_FAILURE = "technical_failure"
