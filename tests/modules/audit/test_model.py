from datetime import UTC

from sqlalchemy import CheckConstraint, ForeignKeyConstraint

from app.modules.audit.enums import AuditAction, AuditOutcome, AuditResourceType
from app.modules.audit.model import AuditEvent, _utc_now


def test_audit_event_uses_closed_values_and_private_persistence_shape() -> None:
    table = AuditEvent.__table__

    assert [item.value for item in AuditAction] == [
        "payment.create",
        "payment.process",
        "payment.cancel",
        "external_transaction.ingest",
        "reconciliation.execute",
    ]
    assert [item.value for item in AuditResourceType] == [
        "payment",
        "external_transaction",
        "reconciliation",
    ]
    assert [item.value for item in AuditOutcome] == ["success", "failure"]
    assert table.c.actor_user_id.nullable is False
    assert table.c.resource_id.nullable is True
    assert table.c.occurred_at.type.timezone is True
    assert any(
        isinstance(item, ForeignKeyConstraint) and item.column_keys == ["actor_user_id"]
        for item in table.constraints
    )
    checks = {
        item.name for item in table.constraints if isinstance(item, CheckConstraint)
    }
    assert {
        "ck_audit_events_failure_reason",
        "ck_audit_events_details_allowlist",
    } <= checks
    assert {"ix_audit_events_actor_occurred_id", "ix_audit_events_actor_action"} <= {
        item.name for item in table.indexes
    }
    assert table.c.details.default is not None
    assert table.c.occurred_at.default is not None
    assert _utc_now().tzinfo is UTC
