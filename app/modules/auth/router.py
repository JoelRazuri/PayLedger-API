from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.exceptions import InactiveUserError, InvalidCredentialsError
from app.modules.auth.schema import RegisterRequest, TokenResponse
from app.modules.auth.service import authenticate_user, register_user
from app.modules.users.exceptions import UserAlreadyExistsError
from app.modules.users.model import User
from app.modules.users.schema import UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_route(
    registration: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        return register_user(db, registration)
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email",
        )


@router.post("/login", response_model=TokenResponse)
def login_route(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    try:
        access_token = authenticate_user(
            db,
            form_data.username,
            form_data.password,
        )
    except InvalidCredentialsError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except InactiveUserError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario se encuentra inactivo",
        )

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def me_route(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user
