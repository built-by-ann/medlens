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
    # Issue #146: how many analyses this document has been included in
    # (len(document.analyses), a property on the model, not a column - see
    # Analysis.document_count for the identical pattern). There is no field
    # for file size: the backend never stores the original uploaded file's
    # bytes, only its extracted raw_text, so no real byte size exists
    # anywhere to expose.
    analysis_count: int = Field(ge=0)


class ClinicalDocumentSummaryResponse(BaseModel):
    """Minimal document identity for citing a source document as supporting
    evidence elsewhere (Issue #46 - see MedicationMentionEvidenceResponse in
    schemas/medication_discrepancy.py), without exposing the full raw_text
    a citation has no need for.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    document_type: str
