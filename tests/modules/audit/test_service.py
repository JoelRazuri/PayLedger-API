from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.modules.audit.enums import AuditAction, AuditOutcome, AuditResourceType
from app.modules.audit.exceptions import AuditEventNotFoundError
from app.modules.audit.model import AuditEvent
from app.modules.audit.schema import AuditEventListQuery
from app.modules.audit.service import get_audit_event, list_audit_events


def test_audit_queries_are_owner_scoped_filtered_and_stable() -> None:
    db = MagicMock(spec=Session)
    query = db.query.return_value
    for name in ("filter", "order_by", "offset", "limit"):
        getattr(query, name).return_value = query
    event = AuditEvent(
        id=8, actor_user_id=7, action=AuditAction.PAYMENT_CREATE,
        resource_type=AuditResourceType.PAYMENT, resource_id=4,
        outcome=AuditOutcome.SUCCESS, details={},
        occurred_at=datetime(2026, 10, 1, 12, tzinfo=UTC))
    query.all.return_value = [event]
    filters = AuditEventListQuery(
        limit=1,
        offset=2,
        action=AuditAction.PAYMENT_CREATE,
        resource_type=AuditResourceType.PAYMENT,
        resource_id=4,
        outcome=AuditOutcome.SUCCESS,
        occurred_from=datetime(2026, 10, 1, 9, tzinfo=UTC),
        occurred_to=datetime(2026, 10, 1, 12, tzinfo=UTC),
    )
    assert list_audit_events(db, 7, filters) == [event]
    assert "actor_user_id" in str(query.filter.call_args_list[0].args[0])
    assert "occurred_at DESC" in str(query.order_by.call_args.args[0])
    assert query.offset.call_args.args == (2,)
    query.first.return_value = None
    with pytest.raises(AuditEventNotFoundError):
        get_audit_event(db, 7, 99)
