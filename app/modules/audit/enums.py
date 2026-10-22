from enum import StrEnum


class AuditAction(StrEnum):
    PAYMENT_CREATE = "payment.create"
    PAYMENT_PROCESS = "payment.process"
    PAYMENT_CANCEL = "payment.cancel"
    EXTERNAL_TRANSACTION_INGEST = "external_transaction.ingest"
    RECONCILIATION_EXECUTE = "reconciliation.execute"


class AuditResourceType(StrEnum):
    PAYMENT = "payment"
    EXTERNAL_TRANSACTION = "external_transaction"
    RECONCILIATION = "reconciliation"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
