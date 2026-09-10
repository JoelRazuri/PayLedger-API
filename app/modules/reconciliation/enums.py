from enum import StrEnum


class ReconciliationResult(StrEnum):
    MATCHED = "matched"
    MISMATCHED = "mismatched"
    UNMATCHED = "unmatched"
