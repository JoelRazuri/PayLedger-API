import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa

MIGRATION_PATH = (
    Path(__file__).parents[2]
    / "alembic"
    / "versions"
    / "b73c6cb6e54a_add_user_credentials_and_active_state.py"
)


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "user_credentials_migration", MIGRATION_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_credentials_migration_follows_current_head() -> None:
    migration = load_migration()

    assert migration.down_revision == "3e81fa4d59d2"


def test_credentials_migration_upgrade_adds_required_columns(monkeypatch) -> None:
    migration = load_migration()
    added_columns: list[sa.Column] = []
    altered_columns: list[tuple[str, str, object]] = []

    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: added_columns.append(column),
    )
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda table, column, **kwargs: altered_columns.append(
            (table, column, kwargs.get("server_default"))
        ),
    )

    migration.upgrade()

    columns = {column.name: column for column in added_columns}
    assert columns["hashed_password"].nullable is False
    assert isinstance(columns["hashed_password"].type, sa.String)
    assert columns["is_active"].nullable is False
    assert str(columns["is_active"].server_default.arg) == "true"
    assert altered_columns == [("users", "is_active", None)]


def test_credentials_migration_downgrade_removes_both_columns(monkeypatch) -> None:
    migration = load_migration()
    dropped_columns: list[tuple[str, str]] = []

    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda table, column: dropped_columns.append((table, column)),
    )

    migration.downgrade()

    assert dropped_columns == [
        ("users", "is_active"),
        ("users", "hashed_password"),
    ]
