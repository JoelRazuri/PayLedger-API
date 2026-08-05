from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.modules.auth.schema import RegisterRequest, TokenResponse
from app.modules.users.model import User
from app.modules.users.schema import UserResponse


@pytest.mark.parametrize("password", ["x" * 8, "x" * 128])
def test_register_request_accepts_password_boundaries(password: str) -> None:
    request = RegisterRequest(
        email="ANA@Example.COM",
        full_name="  Ana   Pérez  ",
        password=password,
    )

    assert request.email == "ana@example.com"
    assert request.full_name == "Ana   Pérez"
    assert request.password == password


@pytest.mark.parametrize("password", ["x" * 7, "x" * 129])
def test_register_request_rejects_password_outside_boundaries(
    password: str,
) -> None:
    with pytest.raises(ValidationError):
        RegisterRequest(
            email="ana@example.com",
            full_name="Ana Pérez",
            password=password,
        )


def test_user_response_excludes_credentials_and_active_state() -> None:
    timestamp = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)
    user = User(
        id=1,
        email="ana@example.com",
        full_name="Ana Pérez",
        hashed_password="argon2-secret-hash",
        is_active=True,
        created_at=timestamp,
        updated_at=timestamp,
    )

    response = UserResponse.model_validate(user)

    assert response.model_dump() == {
        "id": 1,
        "email": "ana@example.com",
        "full_name": "Ana Pérez",
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def test_token_response_has_oauth2_bearer_shape() -> None:
    response = TokenResponse(access_token="signed-token")

    assert response.model_dump() == {
        "access_token": "signed-token",
        "token_type": "bearer",
    }
