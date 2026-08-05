import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def build_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "app_name": "PayLedger API",
        "app_version": "0.1.0",
        "environment": "test",
        "database_url": "postgresql+psycopg://postgres:postgres@localhost/test",
        "jwt_secret": "test-only-secret-that-is-long-enough",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_auth_settings_use_bounded_defaults() -> None:
    settings = build_settings()

    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes == 30


def test_auth_settings_require_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        build_settings(jwt_secret=None)
