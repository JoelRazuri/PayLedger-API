from sqlalchemy.orm import Session

from app.modules.auth.exceptions import InactiveUserError, InvalidCredentialsError
from app.modules.auth.schema import RegisterRequest
from app.modules.auth.security import (
    create_access_token,
    hash_password,
    verify_dummy_password,
    verify_password,
)
from app.modules.users.model import User
from app.modules.users.service import (
    create_user_with_credentials,
    get_user_by_email,
    get_user_by_id,
)


def register_user(db: Session, registration: RegisterRequest) -> User:
    hashed_password = hash_password(registration.password)

    return create_user_with_credentials(
        db=db,
        email=str(registration.email),
        full_name=registration.full_name,
        hashed_password=hashed_password,
    )


def authenticate_user(db: Session, email: str, password: str) -> str:
    user = get_user_by_email(db=db, email=email.lower())

    if user is None:
        verify_dummy_password(password)
        raise InvalidCredentialsError

    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError

    if not user.is_active:
        raise InactiveUserError

    return create_access_token(user_id=user.id)


def resolve_user(db: Session, user_id: int) -> User:
    user = get_user_by_id(db=db, user_id=user_id)

    if user is None:
        raise InvalidCredentialsError

    if not user.is_active:
        raise InactiveUserError

    return user
