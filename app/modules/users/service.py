from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.users.exceptions import UserAlreadyExistsError, UserNotFoundError
from app.modules.users.model import User
from app.modules.users.schema import UserCreate


def create_user(db: Session, user_data: UserCreate) -> User:
    existing_user = get_user_by_email(db=db, email=user_data.email)

    if existing_user:
        raise UserAlreadyExistsError

    user = User(email=user_data.email, full_name=user_data.full_name)

    db.add(user)

    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise UserAlreadyExistsError from error

    db.refresh(user)

    return user


def get_user(db: Session, user_id: int) -> User:
    user = get_user_by_id(db=db, user_id=user_id)

    if not user:
        raise UserNotFoundError

    return user


def get_users(db: Session) -> list[User]:
    return db.query(User).all()


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()
