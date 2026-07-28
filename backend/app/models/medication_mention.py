from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class MedicationMention(Base):
    __tablename__ = "medication_mentions"

    id = Column(Integer, primary_key=True, index=True)
    clinical_document_id = Column(
        Integer,
        ForeignKey("clinical_documents.id"),
        nullable=False,
    )

    medication_name = Column(String, nullable=False)
    normalized_name = Column(String, nullable=True)
    dose = Column(String, nullable=True)
    frequency = Column(String, nullable=True)
    route = Column(String, nullable=True)
    status = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    context_text = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    clinical_document = relationship(
        "ClinicalDocument",
        back_populates="medication_mentions",
    )
    discrepancies = relationship("MedicationDiscrepancy", back_populates="medication_mention")