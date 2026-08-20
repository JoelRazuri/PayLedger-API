class LedgerIntegrityError(Exception):
    """Raised when a payment cannot be represented as a complete journal."""


class LedgerNotFoundError(Exception):
    """Raised when an owner cannot access a journal."""
