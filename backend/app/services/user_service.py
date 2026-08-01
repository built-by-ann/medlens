from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class EmailAlreadyRegisteredError(Exception):
    pass


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)

    if not user or not verify_password(password, user.hashed_password):
        return None

    return user


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


def update_user(db: Session, user: User, user_in: UserUpdate) -> User:
    """Applies only the fields the caller actually set (see UserUpdate) -
    model_fields_set is what distinguishes "email not provided" from "email
    explicitly set to its current value", so a partial update never
    clobbers the other field back to None.
    """
    updates = user_in.model_dump(exclude_unset=True)

    if "email" in updates and updates["email"] != user.email:
        if get_user_by_email(db, updates["email"]):
            raise EmailAlreadyRegisteredError(updates["email"])

        user.email = updates["email"]

    if "name" in updates:
        user.name = updates["name"]

    db.commit()
    db.refresh(user)

    return user
