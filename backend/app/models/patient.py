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

    # Sprint 3.5 will move Medication, ClinicalDocument, and Analysis onto
    # Patient, but none of the three has a patient_id column yet (adding one
    # is explicitly out of scope for this issue). A relationship() cannot be
    # declared without a real foreign key or join condition to configure
    # against, so these are documented here rather than written as live
    # code - writing them anyway would fail at mapper configuration time and
    # break every other model in the app, not just this one:
    #
    # medications = relationship("Medication", back_populates="patient")
    # clinical_documents = relationship("ClinicalDocument", back_populates="patient")
    # analyses = relationship("Analysis", back_populates="patient")
