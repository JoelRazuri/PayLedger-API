class PaymentIdempotencyConflictError(Exception):
    """Raised when a payment key is reused with another payload."""


class PaymentNotFoundError(Exception):
    """Raised when an owned payment cannot be found."""


class PaymentStateConflictError(Exception):
    """Raised when a payment is unavailable for an action."""
