from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    name = Column(String, nullable=True)
    # Nullable so every pre-existing row (created before this column existed)
    # stays valid with no backfill (Issue #191); authentication never uses
    # this, only email/password (see app/services/user_service.py). Real
    # uniqueness is enforced case-insensitively by a functional index on
    # lower(username) (see the Alembic migration), not by `unique=True`
    # here: a plain column-level unique constraint would be case-sensitive
    # and would let "jdoe" and "JDoe" coexist, which the app's own format
    # rules (a-z, A-Z, 0-9, underscore, period; 3-30 chars) don't otherwise
    # rule out.
    username = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Medication, ClinicalDocument, and Analysis are reached only through
    # Patient (see Patient.medications/clinical_documents/analyses); User
    # has no direct relationship to any of them.
    patients = relationship("Patient", back_populates="user")
