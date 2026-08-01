from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

MIN_PASSWORD_LENGTH = 8


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long")

        return value


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Both optional and independently settable, so a caller can update just
    # one field without resending the other - unlike UserCreate, there's no
    # password field here (see app/api/routes/users.py: profile editing is
    # deliberately separate from credential changes, which aren't in scope
    # for this endpoint).
    email: EmailStr | None = None
    name: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str | None
    created_at: datetime
