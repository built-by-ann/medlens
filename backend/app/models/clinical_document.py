from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text
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

    # Issue #58: identifies the original file in whichever StorageService
    # backend is active (a local path or an S3 key; see app/storage/),
    # never a URL, per that feature's own "do not store S3 URLs" rule, so
    # a bucket rename or moving between backends never requires touching
    # stored data. All three are nullable together: a pasted-text document
    # (POST .../clinical-documents, no file at all) and any document
    # created before this column existed have no stored object, and
    # storage_key being null is exactly how the download endpoint
    # distinguishes "nothing to download" from "download failed"; see
    # app/services/clinical_document_service.py.
    storage_key = Column(String, nullable=True)
    content_type = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)

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
