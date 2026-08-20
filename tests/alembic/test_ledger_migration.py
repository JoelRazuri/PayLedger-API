import importlib.util
import os
import subprocess
import uuid
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.core.settings import get_settings

ROOT = Path(__file__).parents[2]
MIGRATION_PATH = ROOT / "alembic" / "versions" / "e8a1d5f3c9b4_create_ledger_tables.py"
ALEMBIC = ROOT / ".venv" / "Scripts" / "alembic.exe"


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("ledger_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_ledger_migration_follows_payments_head_and_declares_reversible_schema() -> (
    None
):
    migration = load_migration()

    assert migration.down_revision == "c4d8e9f0a1b2"
    assert migration.revision == "e8a1d5f3c9b4"

    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "journal_entries" in source
    assert "ledger_entries" in source
    assert "uq_journal_entries_payment_event" in source
    assert "uq_ledger_entries_journal_side" in source
    assert "DEFERRABLE INITIALLY DEFERRED" in source
    assert "DROP TRIGGER" in source


def test_ledger_migration_upgrade_downgrade_upgrade_enforces_deferred_balance() -> None:
    configured = make_url(get_settings().database_url)
    database_name = f"payledger_ledger_test_{uuid.uuid4().hex[:12]}"
    admin_url = configured.set(database="postgres")
    database_url = configured.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
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
        commands = (("upgrade", "head"), ("downgrade", "base"), ("upgrade", "head"))
        for command in commands:
            subprocess.run(
                [str(ALEMBIC), *command], cwd=ROOT, env=environment, check=True
            )

        engine = create_engine(database_url)
        try:
            with engine.connect() as connection:
                with connection.begin():
                    payment_id = _create_processing_payment(connection, "partial")
                with pytest.raises(DBAPIError):
                    with connection.begin():
                        journal_id = connection.execute(
                            text(
                                "INSERT INTO journal_entries "
                                "(payment_id, event_type, amount, currency, "
                                "occurred_at) "
                                "VALUES (:payment_id, 'payment_completed', 12.50, "
                                "'ARS', CURRENT_TIMESTAMP) "
                                "RETURNING id"
                            ),
                            {"payment_id": payment_id},
                        ).scalar_one()
                        connection.execute(
                            text(
                                "INSERT INTO ledger_entries "
                                "(journal_entry_id, side, account, amount, currency) "
                                "VALUES (:journal_id, 'debit', 'PAYMENT_EXPENSE', "
                                "12.50, 'ARS')"
                            ),
                            {"journal_id": journal_id},
                        )
                with connection.begin():
                    payment_id = _create_processing_payment(connection, "balanced")
                    journal_id = connection.execute(
                        text(
                            "INSERT INTO journal_entries "
                            "(payment_id, event_type, amount, currency, "
                            "occurred_at) "
                            "VALUES (:payment_id, 'payment_completed', 12.50, "
                            "'ARS', CURRENT_TIMESTAMP) RETURNING id"
                        ),
                        {"payment_id": payment_id},
                    ).scalar_one()
                    connection.execute(
                        text(
                            "INSERT INTO ledger_entries "
                            "(journal_entry_id, side, account, amount, currency) "
                            "VALUES (:journal_id, 'debit', 'PAYMENT_EXPENSE', "
                            "12.50, 'ARS'), "
                            "(:journal_id, 'credit', 'EXTERNAL_FUNDS', 12.50, "
                            "'ARS')"
                        ),
                        {"journal_id": journal_id},
                    )
                with connection.begin():
                    posting_count = connection.execute(
                        text(
                            "SELECT count(*) FROM ledger_entries "
                            "WHERE journal_entry_id = :journal_id"
                        ),
                        {"journal_id": journal_id},
                    ).scalar_one()
                assert posting_count == 2
                with connection.begin():
                    payment_id = _create_processing_payment(connection, "unbalanced")
                with pytest.raises(DBAPIError):
                    with connection.begin():
                        journal_id = connection.execute(
                            text(
                                "INSERT INTO journal_entries "
                                "(payment_id, event_type, amount, currency, "
                                "occurred_at) "
                                "VALUES (:payment_id, 'payment_completed', 12.50, "
                                "'ARS', CURRENT_TIMESTAMP) "
                                "RETURNING id"
                            ),
                            {"payment_id": payment_id},
                        ).scalar_one()
                        connection.execute(
                            text(
                                "INSERT INTO ledger_entries "
                                "(journal_entry_id, side, account, amount, currency) "
                                "VALUES (:journal_id, 'debit', 'PAYMENT_EXPENSE', "
                                "12.50, 'ARS'), "
                                "(:journal_id, 'credit', 'EXTERNAL_FUNDS', 11.50, "
                                "'ARS')"
                            ),
                            {"journal_id": journal_id},
                        )
        finally:
            engine.dispose()
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


def _create_processing_payment(connection, suffix: str) -> int:
    user_id = connection.execute(
        text(
            "INSERT INTO users "
            "(email, full_name, hashed_password, is_active, created_at, updated_at) "
            "VALUES (:email, 'Ledger Owner', 'hash', true, CURRENT_TIMESTAMP, "
            "CURRENT_TIMESTAMP) RETURNING id"
        ),
        {"email": f"ledger-{suffix}@example.test"},
    ).scalar_one()
    return connection.execute(
        text(
            "INSERT INTO payments "
            "(owner_id, idempotency_key, request_fingerprint, amount, currency, "
            "provider, status, recipient_name, recipient_account_type, "
            "recipient_reference) "
            "VALUES (:owner_id, :key, 'f', 12.50, 'ARS', 'mercado_pago', "
            "'processing', 'Ledger Recipient', 'bank_account', 'CBU-123') "
            "RETURNING id"
        ),
        {"owner_id": user_id, "key": suffix},
    ).scalar_one()
