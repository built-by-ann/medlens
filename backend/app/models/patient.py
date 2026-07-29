from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    external_mrn = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="active")
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="patients")

    # Medication, ClinicalDocument, and Analysis are owned exclusively
    # through Patient - none of them has a user_id of their own (see
    # docs/data-model.md).
    medications = relationship("Medication", back_populates="patient")
    clinical_documents = relationship("ClinicalDocument", back_populates="patient")
    analyses = relationship("Analysis", back_populates="patient")
