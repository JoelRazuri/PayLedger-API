from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.modules.audit import router as audit_router
from app.modules.audit.enums import AuditAction, AuditOutcome, AuditResourceType
from app.modules.audit.exceptions import AuditEventNotFoundError
from app.modules.audit.model import AuditEvent
from app.modules.auth.dependencies import get_current_user
from app.modules.users.model import User


def event() -> AuditEvent:
    return AuditEvent(
        id=8, actor_user_id=7, action=AuditAction.PAYMENT_CREATE,
        resource_type=AuditResourceType.PAYMENT, resource_id=4,
        outcome=AuditOutcome.SUCCESS, details={"replayed": True},
        occurred_at=datetime(2026, 10, 1, 12, tzinfo=UTC))


def test_audit_routes_scope_filter_and_hide_foreign_rows(monkeypatch) -> None:
    app = FastAPI()
    app.include_router(audit_router.router)
    app.dependency_overrides[get_current_user] = lambda: User(id=7)
    app.dependency_overrides[get_db] = lambda: MagicMock()
    listed, detail = MagicMock(return_value=[event()]), MagicMock(return_value=event())
    monkeypatch.setattr(audit_router, "list_audit_events", listed)
    monkeypatch.setattr(audit_router, "get_audit_event", detail)
    with TestClient(app) as client:
        response = client.get("/audit-events?limit=1&offset=2&action=payment.create")
        known = client.get("/audit-events/8")
        invalid = client.get(
            "/audit-events?action=reconciliation.execute&resource_type=payment"
        )
        writes = [
            getattr(client, method)("/audit-events").status_code
            for method in ("post", "patch", "delete")
        ]
        monkeypatch.setattr(
            audit_router,
            "get_audit_event",
            MagicMock(side_effect=AuditEventNotFoundError),
        )
        hidden = client.get("/audit-events/999")
    app.dependency_overrides.clear()

    assert response.json()[0]["occurred_at"] == "2026-10-01T12:00:00Z"
    assert listed.call_args.args[1] == 7 and listed.call_args.args[2].offset == 2
    assert known.json()["id"] == 8 and detail.call_args.args[2] == 8
    assert writes == [405] * 3
    assert (invalid.status_code, hidden.status_code) == (422, 404)
    assert hidden.json() == {"detail": "Evento de auditor\u00eda no encontrado"}
