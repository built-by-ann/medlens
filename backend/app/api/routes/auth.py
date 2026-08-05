import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.schemas.auth import Token, UserLogin
from app.schemas.user import UserCreate, UserResponse
from app.services.user_service import (
    EmailAlreadyRegisteredError,
    UsernameAlreadyRegisteredError,
    authenticate_user,
    create_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(user_in: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    try:
        user = create_user(db, user_in)
    except EmailAlreadyRegisteredError:
        # Never logs the attempted email - by itself this is only
        # informative alongside enough surrounding calls to suggest
        # enumeration, and the resulting 409 already tells the caller (who
        # already knows the email they submitted) everything this log
        # could productively add.
        logger.info(
            "Registration rejected: email already registered",
            extra={"event": "registration_failed"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email is already registered",
        ) from None
    except UsernameAlreadyRegisteredError:
        logger.info(
            "Registration rejected: username already taken",
            extra={"event": "registration_failed"},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This username is already taken",
        ) from None

    logger.info(
        "User registered",
        extra={"event": "user_registered", "user_id": user.id},
    )

    return user


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)) -> Token:
    user = authenticate_user(db, credentials.email, credentials.password)

    if not user:
        # Deliberately never logs the submitted email or password (see
        # this issue's own "never log passwords" requirement) - a failed
        # login with no other identifying detail is still the standard,
        # useful security-monitoring signal (repeated failures, timing),
        # without risking logging a mistyped password someone pasted into
        # the email field by accident.
        logger.warning(
            "Login failed",
            extra={"event": "login_failed"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(data={"sub": str(user.id)})

    logger.info(
        "Login succeeded",
        extra={"event": "login_succeeded", "user_id": user.id},
    )

    return Token(access_token=access_token, token_type="bearer")
