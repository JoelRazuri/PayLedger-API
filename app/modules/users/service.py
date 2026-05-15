from sqlalchemy.orm import Session

from app.modules.users.model import User
from app.modules.users.schema import UserCreate


def create_user(db: Session, user_data: UserCreate) -> User:
    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_users(db: Session) -> list[User]:
    return db.query(User).all()