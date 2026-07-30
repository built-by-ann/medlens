from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.medication_discrepancy import MedicationDiscrepancyDetailResponse


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisCreate(BaseModel):
    clinical_document_ids: list[int] = Field(min_length=1)


class AnalysisCompletedSummary(BaseModel):
    summary: str | None = None
    total_findings: int = Field(ge=0)
    high_severity_findings: int = Field(ge=0)
    medium_severity_findings: int = Field(ge=0)
    low_severity_findings: int = Field(ge=0)
    provider: str | None = None
    model_name: str | None = None


class AnalysisFailure(BaseModel):
    error_message: str = Field(min_length=1)


class AnalysisMedicationMentionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    medication_name: str
    dosage: str | None
    route: str | None
    frequency: str | None
    status: str | None
    notes: str | None


class AnalysisInconsistencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    description: str


class AnalysisDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    status: AnalysisStatus
    provider: str | None
    model_name: str | None
    summary: str | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime | None

    medication_mentions: list[AnalysisMedicationMentionResponse]
    possible_inconsistencies: list[AnalysisInconsistencyResponse]
    # Issue #148: real, structured reconciliation findings, alongside the
    # AI's own unstructured medication_mentions/possible_inconsistencies
    # observations above. Always an empty list rather than omitted when
    # reconciliation found nothing to flag. Issue #46 upgraded each item
    # from MedicationDiscrepancyResponse to MedicationDiscrepancyDetailResponse,
    # nesting the medication/medication_mention evidence so the Analysis
    # Results page can render supporting evidence without a second request.
    medication_discrepancies: list[MedicationDiscrepancyDetailResponse]


class AnalysisSummaryResponse(BaseModel):
    """A single row in a patient's analysis history.

    Deliberately narrower than AnalysisDetailResponse: no medication
    mentions or inconsistencies, since a list view only needs enough to
    identify an analysis and decide whether to open it. document_count is
    computed (len(analysis.clinical_documents)), not a model column, so
    this cannot be built with model_validate the way AnalysisDetailResponse
    is; the route constructs it field by field instead.
    """

    id: int
    patient_id: int
    status: AnalysisStatus
    created_at: datetime
    completed_at: datetime | None
    error_message: str | None
    summary: str | None
    document_count: int = Field(ge=0)
    total_findings: int
    high_severity_findings: int
    medium_severity_findings: int
    low_severity_findings: int
    provider: str | None
    model_name: str | None
