from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.users.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.modules.users.schema import UserCreate, UserResponse
from app.modules.users.service import create_user, get_user, get_users

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user_route(user_data: UserCreate, db: Session = Depends(get_db)):
    try:
        return create_user(db, user_data)

    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un usuario con ese email",
        )


@router.get(
    "",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK,
)
def get_users_route(db: Session = Depends(get_db)):
    return get_users(db)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_user_route(user_id: int, db: Session = Depends(get_db)):
    try:
        return get_user(db=db, user_id=user_id)

    except UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado",
        )
