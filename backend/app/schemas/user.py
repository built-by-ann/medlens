import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

MIN_PASSWORD_LENGTH = 8

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 30
# a-z, A-Z, 0-9, underscore, period only, deliberately no hyphen or other
# punctuation, since the issue's own rules list exactly these characters.
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_.]+$")


def validate_username_format(value: str) -> str:
    """Shared by UserCreate and UserUpdate (see below) so registration and
    profile updates can never enforce different rules for the same field.
    Only format is checked here; uniqueness requires a database lookup, so
    it's enforced separately in app/services/user_service.py, the same
    split already used for email (EmailStr checks format here; email
    uniqueness is a service-layer check raising EmailAlreadyRegisteredError).
    """
    if not (USERNAME_MIN_LENGTH <= len(value) <= USERNAME_MAX_LENGTH):
        raise ValueError(
            f"Username must be between {USERNAME_MIN_LENGTH} and "
            f"{USERNAME_MAX_LENGTH} characters long"
        )

    if not USERNAME_PATTERN.match(value):
        raise ValueError("Username may only contain letters, numbers, underscores, and periods")

    return value


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    username: str
    name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")

        return value

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        return validate_username_format(value)


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # All optional and independently settable, so a caller can update just
    # one field without resending the others; unlike UserCreate, there's no
    # password field here (see app/api/routes/users.py: profile editing is
    # deliberately separate from credential changes, which aren't in scope
    # for this endpoint).
    email: EmailStr | None = None
    name: str | None = None
    username: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return value

        return validate_username_format(value)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str | None
    username: str | None
    created_at: datetime
