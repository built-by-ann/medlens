from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User
from app.schemas.user import UserCreate


class EmailAlreadyRegisteredError(Exception):
    pass


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, user_in: UserCreate) -> User:
    if get_user_by_email(db, user_in.email):
        raise EmailAlreadyRegisteredError(user_in.email)

    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        name=user_in.name,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user
