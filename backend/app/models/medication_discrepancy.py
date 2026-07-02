from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.db.session import Base


class MedicationDiscrepancy(Base):
    __tablename__ = "medication_discrepancies"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey("analyses.id"), nullable=False)

    medication_name = Column(String, nullable=False)
    normalized_name = Column(String, nullable=True)

    source_document_a_id = Column(
        Integer,
        ForeignKey("clinical_documents.id"),
        nullable=False,
    )
    source_document_b_id = Column(
        Integer,
        ForeignKey("clinical_documents.id"),
        nullable=False,
    )

    discrepancy_type = Column(String, nullable=False)
    severity = Column(String, nullable=True)

    ai_explanation = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    resolved = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())