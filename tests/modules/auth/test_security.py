from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.modules.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)


def test_hash_password_uses_one_way_argon2_hash() -> None:
    plaintext = "correct horse battery staple"

    hashed_password = hash_password(plaintext)

    assert hashed_password != plaintext
    assert hashed_password.startswith("$argon2")
    assert verify_password(plaintext, hashed_password) is True


def test_verify_password_rejects_different_password() -> None:
    hashed_password = hash_password("correct password")

    assert verify_password("wrong password", hashed_password) is False


def test_dummy_password_verification_always_rejects_credentials() -> None:
    assert verify_dummy_password("first unknown password") is False
    assert verify_dummy_password("another unknown password") is False


def test_access_token_contains_bounded_safe_claims() -> None:
    issued_at = datetime(2026, 8, 5, 12, 0, tzinfo=UTC)

    token = create_access_token(user_id=42, now=issued_at)
    claims = jwt.decode(
        token,
        options={"verify_signature": False, "verify_exp": False},
    )

    assert claims["sub"] == "42"
    assert datetime.fromtimestamp(claims["exp"], UTC) == issued_at + timedelta(
        minutes=30
    )
    assert "password" not in claims
    assert "hashed_password" not in claims


def test_decode_access_token_returns_user_id_for_valid_token() -> None:
    token = create_access_token(user_id=7)

    assert decode_access_token(token) == 7


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        jwt.encode(
            {"sub": "9", "exp": datetime.now(UTC) - timedelta(minutes=1)},
            "test-only-secret-that-is-long-enough-for-authentication-tests",
            algorithm="HS256",
        ),
        jwt.encode(
            {"sub": "not-an-integer", "exp": datetime.now(UTC) + timedelta(minutes=1)},
            "test-only-secret-that-is-long-enough-for-authentication-tests",
            algorithm="HS256",
        ),
    ],
)
def test_decode_access_token_rejects_unusable_tokens(token: str) -> None:
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)
