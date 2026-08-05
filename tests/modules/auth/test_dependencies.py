from unittest.mock import MagicMock

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.auth.dependencies import get_current_user
from app.modules.auth.exceptions import InactiveUserError, InvalidCredentialsError
from app.modules.users.model import User


def test_get_current_user_rejects_missing_token() -> None:
    db = MagicMock(spec=Session)

    with pytest.raises(HTTPException) as error:
        get_current_user(token=None, db=db)

    assert error.value.status_code == 401
    assert error.value.detail == "No se pudieron validar las credenciales"
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def test_get_current_user_rejects_invalid_token(monkeypatch) -> None:
    db = MagicMock(spec=Session)
    monkeypatch.setattr(
        "app.modules.auth.dependencies.decode_access_token",
        MagicMock(side_effect=jwt.InvalidTokenError),
    )

    with pytest.raises(HTTPException) as error:
        get_current_user(token="invalid-token", db=db)

    assert error.value.status_code == 401
    assert error.value.detail == "No se pudieron validar las credenciales"


def test_get_current_user_rejects_expired_token(monkeypatch) -> None:
    db = MagicMock(spec=Session)
    monkeypatch.setattr(
        "app.modules.auth.dependencies.decode_access_token",
        MagicMock(side_effect=jwt.ExpiredSignatureError),
    )

    with pytest.raises(HTTPException) as error:
        get_current_user(token="expired-token", db=db)

    assert error.value.status_code == 401
    assert error.value.detail == "No se pudieron validar las credenciales"


def test_get_current_user_returns_active_token_user(monkeypatch) -> None:
    db = MagicMock(spec=Session)
    user = User(id=7, is_active=True)
    monkeypatch.setattr(
        "app.modules.auth.dependencies.decode_access_token", MagicMock(return_value=7)
    )
    resolve = MagicMock(return_value=user)
    monkeypatch.setattr("app.modules.auth.dependencies.resolve_user", resolve)

    assert get_current_user(token="valid-token", db=db) is user
    resolve.assert_called_once_with(db=db, user_id=7)


@pytest.mark.parametrize(
    ("domain_error", "status_code", "detail"),
    [
        (
            InvalidCredentialsError(),
            401,
            "No se pudieron validar las credenciales",
        ),
        (InactiveUserError(), 403, "El usuario se encuentra inactivo"),
    ],
)
def test_get_current_user_maps_unusable_users_to_http_errors(
    monkeypatch,
    domain_error: Exception,
    status_code: int,
    detail: str,
) -> None:
    db = MagicMock(spec=Session)
    monkeypatch.setattr(
        "app.modules.auth.dependencies.decode_access_token", MagicMock(return_value=7)
    )
    monkeypatch.setattr(
        "app.modules.auth.dependencies.resolve_user",
        MagicMock(side_effect=domain_error),
    )

    with pytest.raises(HTTPException) as error:
        get_current_user(token="valid-token", db=db)

    assert error.value.status_code == status_code
    assert error.value.detail == detail
