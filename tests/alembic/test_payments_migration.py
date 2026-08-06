import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "c4d8e9f0a1b2_create_payments_table.py"
)


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("payments_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_payments_migration_follows_current_head() -> None:
    migration = load_migration()

    assert migration.down_revision == "b73c6cb6e54a"


def test_payments_migration_creates_reversible_financial_schema(monkeypatch) -> None:
    migration = load_migration()
    created_enums: list[str] = []
    created_tables: list[tuple[str, tuple[object, ...]]] = []
    created_indexes: list[tuple[str, str, tuple[str, ...]]] = []
    dropped_indexes: list[tuple[str, str]] = []
    dropped_tables: list[str] = []
    dropped_enums: list[str] = []

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
        lambda name, table, columns: created_indexes.append(
            (name, table, tuple(columns))
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

    assert created_enums == [
        "payment_currency",
        "payment_provider",
        "payment_status",
        "recipient_account_type",
    ]
    assert created_tables[0][0] == "payments"
    columns = {
        element.name: element
        for element in created_tables[0][1]
        if isinstance(element, sa.Column)
    }
    assert isinstance(columns["amount"].type, sa.Numeric)
    assert columns["amount"].type.precision == 18
    assert columns["amount"].type.scale == 2
    assert any(
        isinstance(element, sa.CheckConstraint) and element.sqltext.text == "amount > 0"
        for element in created_tables[0][1]
    )
    assert any(
        isinstance(element, sa.UniqueConstraint)
        and tuple(element._pending_colargs) == ("owner_id", "idempotency_key")
        for element in created_tables[0][1]
    )
    assert created_indexes == [
        ("ix_payments_owner_created_at", "payments", ("owner_id", "created_at")),
        ("ix_payments_owner_status", "payments", ("owner_id", "status")),
        ("ix_payments_owner_provider", "payments", ("owner_id", "provider")),
        ("ix_payments_owner_currency", "payments", ("owner_id", "currency")),
    ]
    assert dropped_indexes == [
        ("ix_payments_owner_currency", "payments"),
        ("ix_payments_owner_provider", "payments"),
        ("ix_payments_owner_status", "payments"),
        ("ix_payments_owner_created_at", "payments"),
    ]
    assert dropped_tables == ["payments"]
    assert dropped_enums == [
        "recipient_account_type",
        "payment_status",
        "payment_provider",
        "payment_currency",
    ]
