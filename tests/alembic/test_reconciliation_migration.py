import importlib.util
from pathlib import Path
from types import ModuleType

from sqlalchemy import text

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "f4c4e8a1d5f3_add_reconciliation_tables.py"
)


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "reconciliation_migration", MIGRATION_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_reconciliation_migration_follows_ledger_head_and_declares_preflight() -> None:
    migration = load_migration()

    assert migration.revision == "f4c4e8a1d5f3"
    assert migration.down_revision == "e8a1d5f3c9b4"
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "GROUP BY owner_id, provider, provider_payment_id" in source
    assert "HAVING count(*) > 1" in source
    assert "uq_payments_owner_provider_provider_payment_id" in source
    assert "provider_payment_id IS NOT NULL" in source
    assert source.index("_duplicate_payment_references") < source.index("create_table")


def test_reconciliation_migration_builds_named_reversible_schema(monkeypatch) -> None:
    migration = load_migration()
    created_enums: list[str] = []
    created_tables: list[tuple[str, tuple[object, ...]]] = []
    created_indexes: list[tuple[str, str, tuple[str, ...], dict[str, object]]] = []
    dropped_indexes: list[tuple[str, str]] = []
    dropped_tables: list[str] = []
    dropped_enums: list[str] = []

    monkeypatch.setattr(
        migration,
        "_duplicate_payment_references",
        lambda: [],
    )
    monkeypatch.setattr(
        migration,
        "_create_enum",
        lambda enum: created_enums.append(enum.name),
    )
    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *elements: created_tables.append((name, elements)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, table, columns, **kwargs: created_indexes.append(
            (name, table, tuple(columns), kwargs)
        ),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_index",
        lambda name, table_name: dropped_indexes.append((name, table_name)),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_table",
        lambda name: dropped_tables.append(name),
    )
    monkeypatch.setattr(
        migration,
        "_drop_enum",
        lambda enum: dropped_enums.append(enum.name),
    )

    migration.upgrade()
    migration.downgrade()

    assert created_enums == ["reconciliation_result"]
    assert [name for name, _ in created_tables] == [
        "external_transactions",
        "reconciliations",
    ]
    partial_index = created_indexes[-1]
    assert partial_index[:3] == (
        "uq_payments_owner_provider_provider_payment_id",
        "payments",
        ("owner_id", "provider", "provider_payment_id"),
    )
    assert partial_index[3]["unique"] is True
    assert (
        str(partial_index[3]["postgresql_where"]) == "provider_payment_id IS NOT NULL"
    )
    assert [name for name, _, _, _ in created_indexes] == [
        "ix_external_transactions_owner_received_at_id",
        "ix_reconciliations_owner_reconciled_at_id",
        "ix_reconciliations_owner_result_reconciled_at_id",
        "uq_payments_owner_provider_provider_payment_id",
    ]
    assert dropped_indexes == [
        ("uq_payments_owner_provider_provider_payment_id", "payments"),
        ("ix_reconciliations_owner_result_reconciled_at_id", "reconciliations"),
        ("ix_reconciliations_owner_reconciled_at_id", "reconciliations"),
        ("ix_external_transactions_owner_received_at_id", "external_transactions"),
    ]
    assert dropped_tables == ["reconciliations", "external_transactions"]
    assert dropped_enums == ["reconciliation_result"]


def test_reconciliation_migration_aborts_before_ddl_when_payment_references_duplicate(
    monkeypatch,
) -> None:
    migration = load_migration()
    created_tables: list[str] = []
    monkeypatch.setattr(
        migration,
        "_duplicate_payment_references",
        lambda: [(9, "stripe", "provider-9", 2)],
    )
    monkeypatch.setattr(
        migration.op,
        "create_table",
        lambda name, *_elements: created_tables.append(name),
    )

    try:
        migration.upgrade()
    except RuntimeError as error:
        assert str(error) == (
            "Cannot add payment provider reference uniqueness; duplicates found: "
            "owner_id=9, provider=stripe, provider_payment_id=provider-9, count=2"
        )
    else:
        raise AssertionError("Expected duplicate payment references to abort migration")

    assert created_tables == []


def test_reconciliation_migration_cycle_enforces_postgresql_constraints() -> None:
    import os
    import subprocess
    import uuid

    import pytest
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import DBAPIError, SQLAlchemyError

    from app.core.settings import get_settings

    root = Path(__file__).parents[2]
    alembic = root / ".venv" / "Scripts" / "alembic.exe"
    configured = make_url(get_settings().database_url)
    database_name = f"payledger_reconciliation_test_{uuid.uuid4().hex[:12]}"
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
        subprocess.run(
            [str(alembic), "upgrade", "head"], cwd=root, env=environment, check=True
        )

        engine = create_engine(database_url)
        try:
            with engine.begin() as connection:
                owner_id = connection.execute(
                    text(
                        "INSERT INTO users "
                        "(email, full_name, hashed_password, is_active, created_at, "
                        "updated_at) VALUES "
                        "('reconciliation@example.test', 'Owner', 'hash', true, "
                        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) RETURNING id"
                    )
                ).scalar_one()
                payment_id = _insert_payment(
                    connection, owner_id, "payment-1", "provider-payment-1"
                )
                connection.execute(
                    text(
                        "INSERT INTO external_transactions "
                        "(owner_id, provider, external_id, provider_payment_id, "
                        "request_fingerprint, amount, currency, status, "
                        "occurred_at) VALUES (:owner_id, 'stripe', "
                        "'external-1', 'provider-payment-1', "
                        "'f', 12.50, 'ARS', 'completed', CURRENT_TIMESTAMP)"
                    ),
                    {"owner_id": owner_id},
                )
                connection.execute(
                    text(
                        "INSERT INTO reconciliations "
                        "(owner_id, external_transaction_id, payment_id, "
                        "idempotency_key, external_amount, external_currency, "
                        "external_status, local_amount, local_currency, "
                        "local_status, result, "
                        "amount_matches, currency_matches, status_matches) "
                        "VALUES (:owner_id, 1, :payment_id, 'attempt-1', "
                        "12.50, 'ARS', 'completed', 12.50, 'ARS', 'completed', "
                        "'matched', true, true, true)"
                    ),
                    {"owner_id": owner_id, "payment_id": payment_id},
                )

            with pytest.raises(DBAPIError):
                with engine.begin() as connection:
                    _insert_payment(
                        connection, owner_id, "payment-2", "provider-payment-1"
                    )
            with pytest.raises(DBAPIError):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO reconciliations "
                            "(owner_id, external_transaction_id, payment_id, "
                            "idempotency_key, external_amount, external_currency, "
                            "external_status, local_currency, local_status, result, "
                            "amount_matches, currency_matches, status_matches) "
                            "VALUES (:owner_id, 1, :payment_id, "
                            "'attempt-missing-local-amount', 12.50, 'ARS', "
                            "'completed', 'ARS', 'completed', 'matched', "
                            "true, true, true)"
                        ),
                        {"owner_id": owner_id, "payment_id": payment_id},
                    )
            with pytest.raises(DBAPIError):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO external_transactions "
                            "(owner_id, provider, external_id, provider_payment_id, "
                            "request_fingerprint, amount, currency, status, "
                            "occurred_at) VALUES (:owner_id, 'stripe', "
                            "'external-invalid', 'ref', 'f', "
                            "12.50, 'ARS', 'pending', CURRENT_TIMESTAMP)"
                        ),
                        {"owner_id": owner_id},
                    )
            with pytest.raises(DBAPIError):
                with engine.begin() as connection:
                    connection.execute(
                        text(
                            "INSERT INTO reconciliations "
                            "(owner_id, external_transaction_id, payment_id, "
                            "idempotency_key, external_amount, external_currency, "
                            "external_status, result, "
                            "amount_matches, currency_matches, status_matches) "
                            "VALUES (:owner_id, 1, :payment_id, "
                            "'attempt-invalid', 12.50, "
                            "'ARS', 'completed', 'unmatched', true, true, true)"
                        ),
                        {"owner_id": owner_id, "payment_id": payment_id},
                    )
        finally:
            engine.dispose()

        subprocess.run(
            [str(alembic), "downgrade", "e8a1d5f3c9b4"],
            cwd=root,
            env=environment,
            check=True,
        )
        subprocess.run(
            [str(alembic), "upgrade", "head"], cwd=root, env=environment, check=True
        )
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


def _insert_payment(
    connection, owner_id: int, key: str, provider_payment_id: str
) -> int:
    return connection.execute(
        text(
            "INSERT INTO payments "
            "(owner_id, idempotency_key, request_fingerprint, amount, currency, "
            "provider, status, recipient_name, recipient_account_type, "
            "recipient_reference, provider_payment_id) "
            "VALUES (:owner_id, :key, 'f', 12.50, 'ARS', 'stripe', 'completed', "
            "'Recipient', 'bank_account', 'CBU-123', :provider_payment_id) "
            "RETURNING id"
        ),
        {
            "owner_id": owner_id,
            "key": key,
            "provider_payment_id": provider_payment_id,
        },
    ).scalar_one()
