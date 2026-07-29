from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.session import Base

analysis_clinical_documents = Table(
    "analysis_clinical_documents",
    Base.metadata,
    Column(
        "analysis_id",
        Integer,
        ForeignKey("analyses.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "clinical_document_id",
        Integer,
        ForeignKey("clinical_documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)

    status = Column(String, nullable=False, default="pending")

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    summary = Column(Text, nullable=True)

    total_findings = Column(Integer, nullable=False, default=0)
    high_severity_findings = Column(Integer, nullable=False, default=0)
    medium_severity_findings = Column(Integer, nullable=False, default=0)
    low_severity_findings = Column(Integer, nullable=False, default=0)

    provider = Column(String, nullable=True)
    model_name = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    patient = relationship("Patient", back_populates="analyses")
    medication_discrepancies = relationship(
        "MedicationDiscrepancy",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    clinical_documents = relationship(
        "ClinicalDocument",
        secondary=analysis_clinical_documents,
        back_populates="analyses",
    )
    medication_mentions = relationship(
        "AnalysisMedicationMention",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
    possible_inconsistencies = relationship(
        "AnalysisInconsistency",
        back_populates="analysis",
        cascade="all, delete-orphan",
    )
