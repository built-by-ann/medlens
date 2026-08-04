import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.logging_config import set_request_user_id
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.patient import Patient
from app.models.user import User
from app.services.patient_service import get_patient
from app.services.user_service import get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise credentials_exception from None

    user_id = payload.get("sub")

    if user_id is None:
        raise credentials_exception

    try:
        user = get_user_by_id(db, int(user_id))
    except (ValueError, TypeError):
        raise credentials_exception from None

    if user is None:
        raise credentials_exception

    # request.state, not a ContextVar: every dependency and route handler
    # in this app is a plain sync `def` (synchronous SQLAlchemy
    # throughout), and Starlette runs each one via run_in_threadpool,
    # which gives each sync call its own *copy* of the current context -
    # a ContextVar.set() here would never become visible to the
    # request-logging middleware's own (separately-run) code, even though
    # it's logically "the same request". request.state is a plain
    # attribute on the one Request object every dependency shares, so it
    # propagates correctly across that boundary (app/core/logging_config.py).
    set_request_user_id(request, user.id)

    return user


def get_owned_patient(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Patient:
    """Resolves and returns the patient at the `patient_id` path parameter,
    or 404s if it doesn't exist or doesn't belong to the authenticated
    user. Shared by every patient-nested route (e.g. medications) so this
    check is enforced in exactly one place rather than re-implemented per
    resource - a route simply cannot do anything with a patient_id it
    hasn't resolved through here first.
    """
    patient = get_patient(db, current_user.id, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    return patient
