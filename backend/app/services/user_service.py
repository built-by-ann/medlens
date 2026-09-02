from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class EmailAlreadyRegisteredError(Exception):
    pass


class UsernameAlreadyRegisteredError(Exception):
    pass


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_user_by_username(db: Session, username: str) -> User | None:
    """Case-insensitive by design (Issue #191); matches the functional
    unique index on lower(username) the Alembic migration creates, so this
    lookup and the database's own constraint can never disagree about
    whether a username is taken.
    """
    return db.query(User).filter(func.lower(User.username) == username.lower()).first()


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

    if get_user_by_username(db, user_in.username):
        raise UsernameAlreadyRegisteredError(user_in.username)

    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        name=user_in.name,
        username=user_in.username,
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

    if "username" in updates:
        new_username = updates["username"]
        # Re-casing your own username (e.g. "jdoe" -> "JDoe") is not a
        # conflict with yourself; only compare case-insensitively against
        # *other* users, the same rule get_user_by_username enforces.
        already_this_user = (
            new_username is not None
            and user.username is not None
            and new_username.lower() == user.username.lower()
        )

        if new_username is not None and not already_this_user:
            existing = get_user_by_username(db, new_username)
            if existing is not None and existing.id != user.id:
                raise UsernameAlreadyRegisteredError(new_username)

        user.username = new_username

    db.commit()
    db.refresh(user)

    return user
