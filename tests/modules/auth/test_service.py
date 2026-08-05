from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.modules.auth.exceptions import InactiveUserError, InvalidCredentialsError
from app.modules.auth.schema import RegisterRequest
from app.modules.auth.service import authenticate_user, register_user, resolve_user
from app.modules.users.exceptions import UserAlreadyExistsError
from app.modules.users.model import User


def test_register_user_hashes_password_before_persistence(monkeypatch) -> None:
    db = MagicMock(spec=Session)
    request = RegisterRequest(
        email="ANA@Example.COM",
        full_name="Ana Pérez",
        password="plain-password",
    )
    persisted_user = User(id=1, email="ana@example.com", full_name="Ana Pérez")
    persist = MagicMock(return_value=persisted_user)
    monkeypatch.setattr("app.modules.auth.service.hash_password", lambda value: "hash")
    monkeypatch.setattr(
        "app.modules.auth.service.create_user_with_credentials", persist
    )

    result = register_user(db, request)

    assert result is persisted_user
    persist.assert_called_once_with(
        db=db,
        email="ana@example.com",
        full_name="Ana Pérez",
        hashed_password="hash",
    )


def test_register_user_preserves_duplicate_error(monkeypatch) -> None:
    db = MagicMock(spec=Session)
    request = RegisterRequest(
        email="ana@example.com",
        full_name="Ana Pérez",
        password="plain-password",
    )
    monkeypatch.setattr("app.modules.auth.service.hash_password", lambda value: "hash")
    monkeypatch.setattr(
        "app.modules.auth.service.create_user_with_credentials",
        MagicMock(side_effect=UserAlreadyExistsError),
    )

    with pytest.raises(UserAlreadyExistsError):
        register_user(db, request)


def test_authenticate_active_user_returns_access_token(monkeypatch) -> None:
    db = MagicMock(spec=Session)
    user = User(
        id=7,
        email="ana@example.com",
        hashed_password="argon2-hash",
        is_active=True,
    )
    lookup = MagicMock(return_value=user)
    verify = MagicMock(return_value=True)
    create_token = MagicMock(return_value="signed-token")
    monkeypatch.setattr("app.modules.auth.service.get_user_by_email", lookup)
    monkeypatch.setattr("app.modules.auth.service.verify_password", verify)
    monkeypatch.setattr("app.modules.auth.service.create_access_token", create_token)

    token = authenticate_user(db, "ANA@Example.COM", "plain-password")

    assert token == "signed-token"
    lookup.assert_called_once_with(db=db, email="ana@example.com")
    verify.assert_called_once_with("plain-password", "argon2-hash")
    create_token.assert_called_once_with(user_id=7)


def test_authenticate_unknown_email_uses_dummy_verification(monkeypatch) -> None:
    db = MagicMock(spec=Session)
    dummy_verify = MagicMock(return_value=False)
    monkeypatch.setattr(
        "app.modules.auth.service.get_user_by_email", MagicMock(return_value=None)
    )
    monkeypatch.setattr("app.modules.auth.service.verify_dummy_password", dummy_verify)

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db, "unknown@example.com", "plain-password")

    dummy_verify.assert_called_once_with("plain-password")


def test_authenticate_rejects_wrong_password(monkeypatch) -> None:
    db = MagicMock(spec=Session)
    user = User(email="ana@example.com", hashed_password="argon2-hash")
    monkeypatch.setattr(
        "app.modules.auth.service.get_user_by_email", MagicMock(return_value=user)
    )
    monkeypatch.setattr(
        "app.modules.auth.service.verify_password", MagicMock(return_value=False)
    )

    with pytest.raises(InvalidCredentialsError):
        authenticate_user(db, "ana@example.com", "wrong-password")


def test_authenticate_rejects_inactive_user_after_password_check(monkeypatch) -> None:
    db = MagicMock(spec=Session)
    user = User(
        email="ana@example.com",
        hashed_password="argon2-hash",
        is_active=False,
    )
    verify = MagicMock(return_value=True)
    monkeypatch.setattr(
        "app.modules.auth.service.get_user_by_email", MagicMock(return_value=user)
    )
    monkeypatch.setattr("app.modules.auth.service.verify_password", verify)

    with pytest.raises(InactiveUserError):
        authenticate_user(db, "ana@example.com", "plain-password")

    verify.assert_called_once_with("plain-password", "argon2-hash")


def test_resolve_user_returns_active_user(monkeypatch) -> None:
    db = MagicMock(spec=Session)
    user = User(id=7, is_active=True)
    monkeypatch.setattr(
        "app.modules.auth.service.get_user_by_id", MagicMock(return_value=user)
    )

    assert resolve_user(db, 7) is user


@pytest.mark.parametrize(
    ("user", "expected_error"),
    [
        (None, InvalidCredentialsError),
        (User(id=7, is_active=False), InactiveUserError),
    ],
)
def test_resolve_user_rejects_unusable_identity(
    monkeypatch,
    user: User | None,
    expected_error: type[Exception],
) -> None:
    db = MagicMock(spec=Session)
    monkeypatch.setattr(
        "app.modules.auth.service.get_user_by_id", MagicMock(return_value=user)
    )

    with pytest.raises(expected_error):
        resolve_user(db, 7)
