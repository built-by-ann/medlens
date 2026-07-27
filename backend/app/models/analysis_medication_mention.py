from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class AnalysisMedicationMention(Base):
    """A medication as extracted by the AI summary service for one analysis.

    Distinct from MedicationMention, which is scoped to a ClinicalDocument
    and used by the deterministic reconciliation engine. This model is
    scoped to an Analysis and is not matched against the user's Medication
    list; it is a record of what the AI observed, nothing more.
    """

    __tablename__ = "analysis_medication_mentions"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)

    medication_name = Column(String, nullable=False)
    dosage = Column(String, nullable=True)
    route = Column(String, nullable=True)
    frequency = Column(String, nullable=True)
    status = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    analysis = relationship("Analysis", back_populates="medication_mentions")
