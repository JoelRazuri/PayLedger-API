import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.main import app
from app.modules.audit.enums import AuditAction, AuditOutcome, AuditResourceType
from app.modules.audit.model import AuditEvent
from app.modules.audit.service import AuditEventData, stage_event
from app.modules.auth.dependencies import get_current_user
from app.modules.payments import service as payment_service
from app.modules.payments.schema import PaymentCreate
from tests.integration.test_payments_postgres import user

pytest_plugins = ("tests.integration.test_payments_postgres",)


def _payment_request() -> PaymentCreate:
    return PaymentCreate.model_validate(
        {
            "amount": "12.50",
            "currency": "ARS",
            "provider": "mercado_pago",
            "recipient": {
                "name": "Ada Lovelace",
                "account_type": "bank_account",
                "reference": "CBU-123",
            },
        }
    )


def test_concurrent_payment_create_persists_success_and_replay_audit_events(
    sessions, monkeypatch
) -> None:
    setup = sessions()
    try:
        owner = user(setup, 200)
        owner_id = owner.id
    finally:
        setup.close()

    original_find = payment_service._find_by_key
    barrier = threading.Barrier(2)
    lock = threading.Lock()
    initial_reads = 0

    def synchronize_initial_reads(*args, **kwargs):
        nonlocal initial_reads
        found = original_find(*args, **kwargs)
        if found is None:
            with lock:
                initial_reads += 1
                synchronize = initial_reads <= 2
            if synchronize:
                barrier.wait(timeout=5)
        return found

    monkeypatch.setattr(payment_service, "_find_by_key", synchronize_initial_reads)
    first, second = sessions(), sessions()
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    payment_service.create_payment,
                    db,
                    owner_id,
                    "concurrent-audit",
                    _payment_request(),
                )
                for db in (first, second)
            ]
            results = [future.result(timeout=10) for future in futures]
            payment_ids = [result.payment.id for result in results]
    finally:
        first.close()
        second.close()

    verifier = sessions()
    try:
        events = (
            verifier.query(AuditEvent)
            .filter(
                AuditEvent.actor_user_id == owner_id,
                AuditEvent.action == AuditAction.PAYMENT_CREATE,
            )
            .order_by(AuditEvent.id)
            .all()
        )
    finally:
        verifier.close()

    assert len(set(payment_ids)) == 1
    assert sorted(result.replayed for result in results) == [False, True]
    assert [(event.outcome, event.details) for event in events] == [
        (AuditOutcome.SUCCESS, {"status": "pending"}),
        (AuditOutcome.SUCCESS, {"replayed": True}),
    ]


def test_database_rejects_sensitive_unallowlisted_audit_details(sessions) -> None:
    db = sessions()
    try:
        owner = user(db, 201)
        stage_event(
            db,
            AuditEventData(
                actor_user_id=owner.id,
                action=AuditAction.PAYMENT_CREATE,
                resource_type=AuditResourceType.PAYMENT,
                resource_id=1,
                outcome=AuditOutcome.SUCCESS,
                details={"status": "pending"},
            ),
        )
        db.commit()
        db.add(
            AuditEvent(
                actor_user_id=owner.id,
                action=AuditAction.PAYMENT_CREATE,
                resource_type=AuditResourceType.PAYMENT,
                resource_id=2,
                outcome=AuditOutcome.SUCCESS,
                details={"token": "sensitive-value"},
            )
        )
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        events = db.query(AuditEvent).filter_by(actor_user_id=owner.id).all()
    finally:
        db.close()

    assert [event.details for event in events] == [{"status": "pending"}]
    assert all("token" not in event.details for event in events)


def test_database_backed_audit_filters_and_foreign_not_found_are_private(
    sessions,
) -> None:
    db = sessions()
    try:
        owner = user(db, 202)
        foreign = user(db, 203)
        events = [
            AuditEvent(actor_user_id=owner.id, action=AuditAction.PAYMENT_CREATE,
                       resource_type=AuditResourceType.PAYMENT, resource_id=9,
                       outcome=AuditOutcome.SUCCESS, details={},
                       occurred_at=datetime(2026, 1, 1, hour, tzinfo=UTC))
            for hour in (10, 11)
        ]
        events.extend(
            [
                AuditEvent(actor_user_id=foreign.id, action=AuditAction.PAYMENT_CREATE,
                           resource_type=AuditResourceType.PAYMENT, resource_id=9,
                           outcome=AuditOutcome.SUCCESS, details={},
                           occurred_at=datetime(2026, 1, 12, tzinfo=UTC)),
                AuditEvent(actor_user_id=owner.id, action=AuditAction.PAYMENT_PROCESS,
                           resource_type=AuditResourceType.PAYMENT, resource_id=9,
                           outcome=AuditOutcome.SUCCESS, details={},
                           occurred_at=datetime(2026, 1, 12, tzinfo=UTC)),
            ]
        )
        db.add_all(events)
        db.commit()
        expected_event_id = events[0].id
        foreign_event_id = events[2].id
        app.dependency_overrides[get_current_user] = lambda: owner
        app.dependency_overrides[get_db] = lambda: db
        with TestClient(app) as client:
            filtered = client.get(
                "/audit-events",
                params={
                    "limit": 1, "offset": 1, "action": "payment.create",
                    "resource_type": "payment", "resource_id": 9,
                    "outcome": "success", "occurred_from": "2026-01-01T09:00:00Z",
                    "occurred_to": "2026-01-01T12:00:00Z",
                },
            )
            foreign_response = client.get(f"/audit-events/{foreign_event_id}")
            absent_response = client.get("/audit-events/999999")
    finally:
        app.dependency_overrides.clear()
        db.close()

    assert [item["id"] for item in filtered.json()] == [expected_event_id]
    assert (foreign_response.status_code, foreign_response.json()) == (
        absent_response.status_code,
        absent_response.json(),
    ) == (404, {"detail": "Evento de auditoría no encontrado"})
