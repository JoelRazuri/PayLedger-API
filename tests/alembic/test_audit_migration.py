import os
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, SQLAlchemyError

from app.core.settings import get_settings

ROOT = Path(__file__).parents[2]
ALEMBIC = ROOT / ".venv/Scripts/alembic.exe"


def test_audit_migration_rejects_mutation_after_upgrade_downgrade_cycle() -> None:
    configured = make_url(get_settings().database_url)
    name = f"payledger_audit_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(
        configured.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    database = configured.set(database=name)
    try:
        try:
            with admin.connect() as connection:
                connection.execute(text(f'CREATE DATABASE "{name}"'))
        except SQLAlchemyError as error:
            pytest.skip(
                f"PostgreSQL integration unavailable: {error.__class__.__name__}"
            )
        env = os.environ | {
            "DATABASE_URL": database.render_as_string(hide_password=False)
        }
        for command in (
            ("upgrade", "head"),
            ("downgrade", "f4c4e8a1d5f3"),
            ("upgrade", "head"),
        ):
            subprocess.run([str(ALEMBIC), *command], cwd=ROOT, env=env, check=True)
        engine = create_engine(database)
        try:
            with engine.begin() as connection:
                user_id = connection.execute(
                    text(
                        "INSERT INTO users (email, full_name, hashed_password, "
                        "is_active, created_at, updated_at) VALUES "
                        "('audit@example.test', 'Audit', 'hash', true, "
                        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) RETURNING id"
                    )
                ).scalar_one()
                event_id = connection.execute(
                    text(
                        "INSERT INTO audit_events (actor_user_id, action, "
                        "resource_type, outcome, details, occurred_at) VALUES "
                        "(:user_id, 'payment.create', 'payment', 'success', "
                        "'{}'::jsonb, CURRENT_TIMESTAMP) RETURNING id"
                    ),
                    {"user_id": user_id},
                ).scalar_one()
            for statement in (
                "UPDATE audit_events SET details = '{}'::jsonb WHERE id = :id",
                "DELETE FROM audit_events WHERE id = :id",
            ):
                with pytest.raises(DBAPIError):
                    with engine.begin() as connection:
                        connection.execute(text(statement), {"id": event_id})
        finally:
            engine.dispose()
    finally:
        with admin.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()
