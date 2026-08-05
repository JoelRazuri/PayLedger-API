from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.settings import get_settings

password_hash = PasswordHash.recommended()
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$GKZBKDDWZsg87bieGnDeMA$"
    "IfD0sm0dQBU70x6VIVz2cPP5/mzeCjPx8cdKqMHkoUQ"
)


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def verify_dummy_password(password: str) -> bool:
    password_hash.verify(password, DUMMY_PASSWORD_HASH)
    return False


def create_access_token(user_id: int, now: datetime | None = None) -> str:
    settings = get_settings()
    issued_at = now or datetime.now(UTC)
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    claims = {"sub": str(user_id), "exp": expires_at}

    return jwt.encode(
        claims,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> int:
    settings = get_settings()
    claims = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )

    try:
        return int(claims["sub"])
    except (KeyError, TypeError, ValueError) as error:
        raise jwt.InvalidTokenError("Invalid token subject") from error
