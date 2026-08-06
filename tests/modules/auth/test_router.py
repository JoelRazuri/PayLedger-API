from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.auth import router as auth_router
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.exceptions import InactiveUserError, InvalidCredentialsError
from app.modules.users.exceptions import UserAlreadyExistsError
from app.modules.users.model import User

client = TestClient(app)


def build_user(**overrides: object) -> User:
    timestamp = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    values: dict[str, object] = {
        "id": 7,
        "email": "ana@example.com",
        "full_name": "Ana Pérez",
        "hashed_password": "argon2-hash",
        "is_active": True,
        "created_at": timestamp,
        "updated_at": timestamp,
    }
    values.update(overrides)
    return User(**values)


def test_register_returns_safe_user_without_starting_session(monkeypatch) -> None:
    register = MagicMock(return_value=build_user())
    monkeypatch.setattr(auth_router, "register_user", register)
    response = client.post(
        "/auth/register",
        json={
            "email": "ANA@Example.COM",
            "full_name": "  Ana Pérez  ",
            "password": "plain-password",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": 7,
        "email": "ana@example.com",
        "full_name": "Ana Pérez",
        "created_at": "2026-08-05T12:00:00Z",
        "updated_at": "2026-08-05T12:00:00Z",
    }
    assert "password" not in response.text
    assert "token" not in response.text
    registration = register.call_args.args[1]
    assert registration.email == "ana@example.com"
    assert registration.full_name == "Ana Pérez"


def test_register_maps_duplicate_email_to_spanish_conflict(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_router,
        "register_user",
        MagicMock(side_effect=UserAlreadyExistsError),
    )
    response = client.post(
        "/auth/register",
        json={
            "email": "ana@example.com",
            "full_name": "Ana Pérez",
            "password": "plain-password",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Ya existe un usuario con ese email"}


@pytest.mark.parametrize(
    ("full_name", "expected_message"),
    [
        ("", "El nombre completo debe tener al menos 2 caracteres"),
        ("   ", "El nombre completo debe tener al menos 2 caracteres"),
        ("A", "El nombre completo debe tener al menos 2 caracteres"),
        ("x" * 256, "El nombre completo no puede superar los 255 caracteres"),
    ],
)
def test_register_rejects_invalid_full_name_before_service(
    monkeypatch,
    full_name: str,
    expected_message: str,
) -> None:
    register = MagicMock(side_effect=AssertionError("service must not run"))
    monkeypatch.setattr(auth_router, "register_user", register)
    response = client.post(
        "/auth/register",
        json={
            "email": "ana@example.com",
            "full_name": full_name,
            "password": "plain-password",
        },
    )

    assert response.status_code == 422
    assert expected_message in response.text
    register.assert_not_called()


@pytest.mark.parametrize("password", ["x" * 7, "x" * 129])
def test_register_rejects_invalid_password_before_service(
    monkeypatch,
    password: str,
) -> None:
    register = MagicMock(side_effect=AssertionError("service must not run"))
    monkeypatch.setattr(auth_router, "register_user", register)
    response = client.post(
        "/auth/register",
        json={
            "email": "ana@example.com",
            "full_name": "Ana Pérez",
            "password": password,
        },
    )

    assert response.status_code == 422
    register.assert_not_called()


def test_login_accepts_oauth2_form_and_returns_bearer_token(monkeypatch) -> None:
    authenticate = MagicMock(return_value="signed-token")
    monkeypatch.setattr(auth_router, "authenticate_user", authenticate)
    response = client.post(
        "/auth/login",
        data={"username": "ANA@Example.COM", "password": "plain-password"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "signed-token",
        "token_type": "bearer",
    }
    assert authenticate.call_args.args[1:] == (
        "ANA@Example.COM",
        "plain-password",
    )


def test_login_maps_invalid_credentials_to_spanish_unauthorized(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_router,
        "authenticate_user",
        MagicMock(side_effect=InvalidCredentialsError),
    )
    response = client.post(
        "/auth/login",
        data={"username": "ana@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Email o contraseña incorrectos"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_login_maps_inactive_user_to_spanish_forbidden(monkeypatch) -> None:
    monkeypatch.setattr(
        auth_router,
        "authenticate_user",
        MagicMock(side_effect=InactiveUserError),
    )
    response = client.post(
        "/auth/login",
        data={"username": "ana@example.com", "password": "plain-password"},
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "El usuario se encuentra inactivo"}


def test_me_returns_safe_authenticated_profile() -> None:
    app.dependency_overrides[get_current_user] = lambda: build_user()
    try:
        response = client.get("/auth/me", headers={"Authorization": "Bearer token"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == 7
    assert response.json()["email"] == "ana@example.com"
    assert "hashed_password" not in response.text
    assert "is_active" not in response.text


def test_me_rejects_missing_bearer_token_in_spanish() -> None:
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "No se pudieron validar las credenciales"}


def test_me_rejects_invalid_bearer_token_in_spanish() -> None:
    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "No se pudieron validar las credenciales"}
