import os
import subprocess
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import get_db
from app.core.settings import get_settings
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.payments.enums import (
    Currency,
    PaymentProcessScenario,
    PaymentProvider,
    PaymentStatus,
    RecipientAccountType,
)
from app.modules.payments.exceptions import (
    PaymentStateConflictError,
)
from app.modules.payments.model import Payment
from app.modules.payments.provider import SandboxPaymentProvider
from app.modules.payments.schema import PaymentListQuery
from app.modules.payments.service import (
    cancel_payment,
    get_payment,
    list_payments,
    process_payment,
)
from app.modules.users.model import User

ROOT = Path(__file__).parents[2]
ALEMBIC = ROOT / ".venv" / "Scripts" / "alembic.exe"


@pytest.fixture(scope="module")
def payment_database() -> URL:
    configured = make_url(get_settings().database_url)
    database_name = f"payledger_payments_test_{uuid.uuid4().hex[:12]}"
    admin_engine = create_engine(
        configured.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    database_url = configured.set(database=database_name)
    created = False
    try:
        try:
            with admin_engine.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{database_name}"'))
            created = True
        except SQLAlchemyError as error:
            pytest.skip(
                f"PostgreSQL integration unavailable: {error.__class__.__name__}"
            )
        environment = os.environ | {
            "DATABASE_URL": database_url.render_as_string(hide_password=False)
        }
        subprocess.run(
            [str(ALEMBIC), "upgrade", "head"], cwd=ROOT, env=environment, check=True
        )
        yield database_url
    finally:
        if created:
            with admin_engine.connect() as connection:
                connection.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :name AND pid <> pg_backend_pid()"
                    ),
                    {"name": database_name},
                )
                connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin_engine.dispose()


@pytest.fixture
def sessions(payment_database: URL):
    engine = create_engine(payment_database)
    factory = sessionmaker(bind=engine)
    try:
        yield factory
    finally:
        engine.dispose()


def user(db: Session, number: int) -> User:
    value = User(
        email=f"owner-{number}@example.test",
        full_name=f"Owner {number}",
        hashed_password="hash",
    )
    db.add(value)
    db.commit()
    db.refresh(value)
    return value


def pending_payment(
    db: Session,
    owner: User,
    key: str,
    created_at: datetime | None = None,
) -> Payment:
    value = Payment(
        owner_id=owner.id,
        idempotency_key=key,
        request_fingerprint="f" * 64,
        amount="12.50",
        currency=Currency.ARS,
        provider=PaymentProvider.MERCADO_PAGO,
        status=PaymentStatus.PENDING,
        recipient_name="Ada Lovelace",
        recipient_account_type=RecipientAccountType.BANK_ACCOUNT,
        recipient_reference="CBU-123",
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(value)
    db.commit()
    db.refresh(value)
    return value


def test_payment_snapshot_has_no_update_or_delete_api(sessions) -> None:
    db = sessions()
    try:
        owner = user(db, 1)
        payment = pending_payment(db, owner, "immutable")
        app.dependency_overrides[get_current_user] = lambda: owner
        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:
                patched = client.patch(f"/payments/{payment.id}", json={"amount": "99"})
                deleted = client.delete(f"/payments/{payment.id}")
        finally:
            app.dependency_overrides.clear()
        db.expire(payment)
        persisted = get_payment(db, owner.id, payment.id)
    finally:
        db.close()

    assert (patched.status_code, deleted.status_code) == (405, 405)
    assert persisted.recipient_reference == "CBU-123"
    assert persisted.amount == Decimal("12.50")


def test_listing_is_newest_first_and_foreign_actions_are_hidden(sessions) -> None:
    db = sessions()
    try:
        owner = user(db, 2)
        foreign_owner = user(db, 3)
        older = pending_payment(db, owner, "older", datetime(2026, 1, 1, tzinfo=UTC))
        newer = pending_payment(db, owner, "newer", datetime(2026, 1, 2, tzinfo=UTC))
        foreign = pending_payment(db, foreign_owner, "foreign")

        listed = list_payments(db, owner.id, PaymentListQuery(limit=10))
        app.dependency_overrides[get_current_user] = lambda: owner
        app.dependency_overrides[get_db] = lambda: db
        try:
            with TestClient(app) as client:
                foreign_process = client.post(
                    f"/payments/{foreign.id}/process",
                    json={"simulation_scenario": "success"},
                )
                foreign_cancel = client.post(f"/payments/{foreign.id}/cancel")
        finally:
            app.dependency_overrides.clear()

        cancelled = cancel_payment(db, owner.id, older.id)
        db.refresh(cancelled)
        listed_ids = [payment.id for payment in listed]
        expected_ids = [newer.id, older.id]
        cancelled_status = cancelled.status
    finally:
        db.close()

    assert listed_ids == expected_ids
    assert (foreign_process.status_code, foreign_cancel.status_code) == (404, 404)
    assert cancelled_status is PaymentStatus.CANCELLED


class BlockingProvider:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def process(self, payment: Payment, scenario: PaymentProcessScenario):
        self.entered.set()
        assert self.release.wait(timeout=5)
        return SandboxPaymentProvider().process(payment, scenario)


def test_two_sessions_allow_only_one_processing_claim(sessions) -> None:
    setup = sessions()
    try:
        owner = user(setup, 4)
        payment = pending_payment(setup, owner, "concurrency")
        owner_id = owner.id
        payment_id = payment.id
    finally:
        setup.close()

    provider = BlockingProvider()
    first = sessions()
    second = sessions()
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            winner = executor.submit(
                process_payment,
                first,
                owner_id,
                payment_id,
                PaymentProcessScenario.SUCCESS,
                provider,
            )
            assert provider.entered.wait(timeout=5)
            with pytest.raises(PaymentStateConflictError):
                process_payment(
                    second,
                    owner_id,
                    payment_id,
                    PaymentProcessScenario.SUCCESS,
                    SandboxPaymentProvider(),
                )
            provider.release.set()
            completed = winner.result(timeout=5)
    finally:
        first.close()
        second.close()

    assert completed.status is PaymentStatus.COMPLETED
