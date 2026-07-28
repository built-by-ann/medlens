from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Nullable during the Sprint 3.5 migration period: both user_id and
    # patient_id coexist until a later issue backfills every row and drops
    # user_id. See app/services/patient_backfill_service.py.
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True, index=True)

    medication_name = Column(String, nullable=False)
    dose = Column(String, nullable=False)
    route = Column(String, nullable=False)
    frequency = Column(String, nullable=False)
    status = Column(String, nullable=False)
    source = Column(String, nullable=False)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="medications")
    patient = relationship("Patient", back_populates="medications")
    discrepancies = relationship("MedicationDiscrepancy", back_populates="medication")
