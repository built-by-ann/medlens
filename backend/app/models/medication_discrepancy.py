from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class MedicationDiscrepancy(Base):
    __tablename__ = "medication_discrepancies"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)
    medication_id = Column(
        Integer,
        ForeignKey("medications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    medication_mention_id = Column(
        Integer,
        ForeignKey("medication_mentions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    discrepancy_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)

    title = Column(String, nullable=False)
    ai_explanation = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)

    expected_value = Column(String, nullable=True)
    observed_value = Column(String, nullable=True)

    resolution_status = Column(String, nullable=False, default="open")

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    analysis = relationship("Analysis", back_populates="medication_discrepancies")
    medication = relationship("Medication", back_populates="discrepancies")
    medication_mention = relationship("MedicationMention", back_populates="discrepancies")
