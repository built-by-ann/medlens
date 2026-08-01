from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base


class ClinicalDocument(Base):
    __tablename__ = "clinical_documents"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)

    document_type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    raw_text = Column(Text, nullable=False)
    file_name = Column(String, nullable=True)
    file_type = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    patient = relationship("Patient", back_populates="clinical_documents")
    medication_mentions = relationship(
        "MedicationMention",
        back_populates="clinical_document",
        cascade="all, delete-orphan",
    )
    analyses = relationship(
        "Analysis",
        secondary="analysis_clinical_documents",
        back_populates="clinical_documents",
    )

    @property
    def analysis_count(self) -> int:
        return len(self.analyses)
