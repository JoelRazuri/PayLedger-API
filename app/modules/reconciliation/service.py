import json
from dataclasses import dataclass
from hashlib import sha256

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session

from app.modules.reconciliation.exceptions import (
    ExternalTransactionConflictError,
    ExternalTransactionNotFoundError,
)
from app.modules.reconciliation.model import ExternalTransaction
from app.modules.reconciliation.schema import (
    ExternalTransactionCreate,
    ExternalTransactionListQuery,
)

_EXTERNAL_TRANSACTION_UNIQUE = "uq_external_transactions_owner_provider_external_id"


@dataclass(frozen=True)
class ExternalTransactionCreation:
    external_transaction: ExternalTransaction
    replayed: bool


def external_transaction_fingerprint(request: ExternalTransactionCreate) -> str:
    payload = {
        "amount": f"{request.amount:.2f}",
        "currency": request.currency.value,
        "external_id": request.external_id,
        "occurred_at": request.occurred_at.isoformat(timespec="microseconds").replace(
            "+00:00", "Z"
        ),
        "provider": request.provider.value,
        "provider_payment_id": request.provider_payment_id,
        "status": request.status.value,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode()).hexdigest()


def create_external_transaction(
    db: Session,
    owner_id: int,
    request: ExternalTransactionCreate,
) -> ExternalTransactionCreation:
    fingerprint = external_transaction_fingerprint(request)
    existing = _find_external_transaction(
        db, owner_id, request.provider.value, request.external_id
    )
    if existing is not None:
        return _replay_or_conflict(existing, fingerprint)

    external_transaction = ExternalTransaction(
        owner_id=owner_id,
        provider=request.provider,
        external_id=request.external_id,
        provider_payment_id=request.provider_payment_id,
        request_fingerprint=fingerprint,
        amount=request.amount,
        currency=request.currency,
        status=request.status,
        occurred_at=request.occurred_at,
    )
    try:
        with db.begin_nested():
            db.add(external_transaction)
            db.flush()
    except IntegrityError as error:
        if _constraint_name(error) == _EXTERNAL_TRANSACTION_UNIQUE:
            winner = _find_external_transaction(
                db, owner_id, request.provider.value, request.external_id
            )
            if winner is not None:
                return _replay_or_conflict(winner, fingerprint)
        db.rollback()
        raise

    db.commit()
    db.refresh(external_transaction)
    return ExternalTransactionCreation(external_transaction, replayed=False)


def get_external_transaction(
    db: Session,
    owner_id: int,
    external_transaction_id: int,
) -> ExternalTransaction:
    external_transaction = (
        _owned_query(db, owner_id)
        .filter(ExternalTransaction.id == external_transaction_id)
        .first()
    )
    if external_transaction is None:
        raise ExternalTransactionNotFoundError
    return external_transaction


def list_external_transactions(
    db: Session,
    owner_id: int,
    filters: ExternalTransactionListQuery,
) -> list[ExternalTransaction]:
    return (
        _owned_query(db, owner_id)
        .order_by(
            ExternalTransaction.received_at.desc(),
            ExternalTransaction.id.desc(),
        )
        .offset(filters.offset)
        .limit(filters.limit)
        .all()
    )


def _find_external_transaction(
    db: Session,
    owner_id: int,
    provider: str,
    external_id: str,
) -> ExternalTransaction | None:
    return (
        _owned_query(db, owner_id)
        .filter(
            ExternalTransaction.provider == provider,
            ExternalTransaction.external_id == external_id,
        )
        .first()
    )


def _owned_query(db: Session, owner_id: int) -> Query:
    return db.query(ExternalTransaction).filter(
        ExternalTransaction.owner_id == owner_id
    )


def _replay_or_conflict(
    external_transaction: ExternalTransaction,
    fingerprint: str,
) -> ExternalTransactionCreation:
    if external_transaction.request_fingerprint != fingerprint:
        raise ExternalTransactionConflictError
    return ExternalTransactionCreation(external_transaction, replayed=True)


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostics = getattr(error.orig, "diag", None)
    return getattr(diagnostics, "constraint_name", None)
