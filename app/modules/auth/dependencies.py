from typing import Annotated, Never

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.exceptions import InactiveUserError, InvalidCredentialsError
from app.modules.auth.security import decode_access_token
from app.modules.auth.service import resolve_user
from app.modules.users.model import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if token is None:
        raise_credentials_exception()

    try:
        user_id = decode_access_token(token)
        return resolve_user(db=db, user_id=user_id)
    except jwt.InvalidTokenError, InvalidCredentialsError:
        raise_credentials_exception()
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario se encuentra inactivo",
        )


def raise_credentials_exception() -> Never:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No se pudieron validar las credenciales",
        headers={"WWW-Authenticate": "Bearer"},
    )
