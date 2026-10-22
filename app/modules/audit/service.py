from dataclasses import dataclass
from datetime import UTC

from sqlalchemy.orm import Query, Session

from app.modules.audit.enums import AuditAction, AuditOutcome, AuditResourceType
from app.modules.audit.exceptions import AuditEventNotFoundError
from app.modules.audit.model import AuditEvent
from app.modules.audit.schema import AuditEventListQuery


@dataclass(frozen=True)
class AuditEventData:
    actor_user_id: int
    action: AuditAction
    resource_type: AuditResourceType
    resource_id: int | None
    outcome: AuditOutcome
    details: dict[str, object]
    reason_code: str | None = None


_DETAIL_KEYS = {
    AuditAction.PAYMENT_CREATE: frozenset({"replayed", "status"}),
    AuditAction.PAYMENT_PROCESS: frozenset({"replayed", "status"}),
    AuditAction.PAYMENT_CANCEL: frozenset({"replayed", "status"}),
    AuditAction.EXTERNAL_TRANSACTION_INGEST: frozenset({"replayed", "result"}),
    AuditAction.RECONCILIATION_EXECUTE: frozenset({"replayed", "result"}),
}


def stage_event(db: Session, event: AuditEventData) -> None:
    if event.details.keys() - _DETAIL_KEYS[event.action]:
        raise ValueError("Audit details are not allowlisted for this action")
    db.add(
        AuditEvent(
            actor_user_id=event.actor_user_id,
            action=event.action,
            resource_type=event.resource_type,
            resource_id=event.resource_id,
            outcome=event.outcome,
            reason_code=event.reason_code,
            details=event.details,
        )
    )


def list_audit_events(
    db: Session, actor_user_id: int, filters: AuditEventListQuery
) -> list[AuditEvent]:
    query = _owned_query(db, actor_user_id)
    if filters.action is not None:
        query = query.filter(AuditEvent.action == filters.action)
    if filters.resource_type is not None:
        query = query.filter(AuditEvent.resource_type == filters.resource_type)
    if filters.resource_id is not None:
        query = query.filter(AuditEvent.resource_id == filters.resource_id)
    if filters.outcome is not None:
        query = query.filter(AuditEvent.outcome == filters.outcome)
    if filters.occurred_from is not None:
        query = query.filter(AuditEvent.occurred_at >= filters.occurred_from)
    if filters.occurred_to is not None:
        query = query.filter(AuditEvent.occurred_at <= filters.occurred_to)
    events = query.order_by(AuditEvent.occurred_at.desc(), AuditEvent.id.desc())
    page = events.offset(filters.offset).limit(filters.limit)
    return [_normalize_time(event) for event in page.all()]


def get_audit_event(db: Session, actor_user_id: int, audit_event_id: int) -> AuditEvent:
    query = _owned_query(db, actor_user_id)
    event = query.filter(AuditEvent.id == audit_event_id).first()
    if event is None:
        raise AuditEventNotFoundError
    return _normalize_time(event)


def _owned_query(db: Session, actor_user_id: int) -> Query:
    return db.query(AuditEvent).filter(AuditEvent.actor_user_id == actor_user_id)


def _normalize_time(event: AuditEvent) -> AuditEvent:
    event.occurred_at = event.occurred_at.astimezone(UTC)
    return event
