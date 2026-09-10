class ExternalTransactionConflictError(Exception):
    """Raised when external evidence identity is reused with another payload."""


class ExternalTransactionNotFoundError(Exception):
    """Raised when owned external evidence cannot be found."""


class ReconciliationConflictError(Exception):
    """Raised when an idempotency key is reused for another evidence item."""


class ReconciliationNotFoundError(Exception):
    """Raised when an owned reconciliation attempt cannot be found."""
