from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClinicalDocumentCreate(BaseModel):
    document_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)


class ClinicalDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    document_type: str
    title: str
    raw_text: str
    file_name: str | None
    file_type: str | None
    created_at: datetime
    updated_at: datetime | None


class ClinicalDocumentSummaryResponse(BaseModel):
    """Minimal document identity for citing a source document as supporting
    evidence elsewhere (see MedicationMentionEvidenceResponse), without
    exposing the full raw_text a citation has no need for.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    document_type: str
