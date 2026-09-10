class ExternalTransactionConflictError(Exception):
    """Raised when external evidence identity is reused with another payload."""


class ExternalTransactionNotFoundError(Exception):
    """Raised when owned external evidence cannot be found."""
