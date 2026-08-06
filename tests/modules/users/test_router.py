from datetime import UTC, datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.main import app
from app.modules.users import router as users_router
from app.modules.users.model import User

client = TestClient(app)


def test_get_users_remains_public(monkeypatch) -> None:
    monkeypatch.setattr(users_router, "get_users", MagicMock(return_value=[]))

    response = client.get("/users")

    assert response.status_code == 200
    assert response.json() == []


def test_get_user_remains_public(monkeypatch) -> None:
    timestamp = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    user = User(
        id=7,
        email="ana@example.com",
        full_name="Ana Pérez",
        hashed_password="argon2-hash",
        is_active=True,
        created_at=timestamp,
        updated_at=timestamp,
    )
    monkeypatch.setattr(users_router, "get_user", MagicMock(return_value=user))

    response = client.get("/users/7")

    assert response.status_code == 200
    assert response.json()["id"] == 7
    assert "hashed_password" not in response.text


def test_post_users_is_not_available() -> None:
    response = client.post(
        "/users",
        json={
            "email": "ana@example.com",
            "full_name": "Ana Pérez",
            "password": "plain-password",
        },
    )

    assert response.status_code == 405
