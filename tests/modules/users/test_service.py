from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.users.exceptions import UserAlreadyExistsError
from app.modules.users.model import User
from app.modules.users.service import (
    create_user_with_credentials,
    get_user_by_email,
)


def test_get_user_by_email_normalizes_email_before_querying() -> None:
    db = MagicMock(spec=Session)
    expected_user = User(email="ana@example.com")
    db.query.return_value.filter.return_value.first.return_value = expected_user

    result = get_user_by_email(db, "ANA@Example.COM")
    expression = db.query.return_value.filter.call_args.args[0]

    assert result is expected_user
    assert expression.right.value == "ana@example.com"


def test_create_user_with_credentials_persists_only_the_hash() -> None:
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.first.return_value = None

    user = create_user_with_credentials(
        db=db,
        email="ANA@Example.COM",
        full_name="Ana Pérez",
        hashed_password="argon2-hash",
    )

    assert user.email == "ana@example.com"
    assert user.full_name == "Ana Pérez"
    assert user.hashed_password == "argon2-hash"
    assert user.is_active is None
    db.add.assert_called_once_with(user)
    db.commit.assert_called_once_with()
    db.refresh.assert_called_once_with(user)


def test_create_user_with_credentials_rejects_existing_normalized_email() -> None:
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.first.return_value = User(
        email="ana@example.com"
    )

    with pytest.raises(UserAlreadyExistsError):
        create_user_with_credentials(
            db=db,
            email="ANA@Example.COM",
            full_name="Ana Pérez",
            hashed_password="argon2-hash",
        )

    db.add.assert_not_called()
    db.commit.assert_not_called()


def test_create_user_with_credentials_rolls_back_unique_race() -> None:
    db = MagicMock(spec=Session)
    db.query.return_value.filter.return_value.first.return_value = None
    db.commit.side_effect = IntegrityError("insert", {}, Exception("duplicate"))

    with pytest.raises(UserAlreadyExistsError):
        create_user_with_credentials(
            db=db,
            email="ana@example.com",
            full_name="Ana Pérez",
            hashed_password="argon2-hash",
        )

    db.rollback.assert_called_once_with()
