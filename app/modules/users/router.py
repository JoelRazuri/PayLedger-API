from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.modules.users.schema import UserCreate, UserResponse
from app.modules.users.service import create_user, get_users
from app.core.database import get_db


router = APIRouter(
    prefix="/users",
    tags=["Users"],
)

@router.post(
    "",
    response_model=UserResponse,
)
def create_user_route(
    user_data: UserCreate,
    db: Session = Depends(get_db),
):
    return create_user(db, user_data)


@router.get(
    "",
    response_model=list[UserResponse],
)
def get_users_route(
    db: Session = Depends(get_db),
):
    return get_users(db)