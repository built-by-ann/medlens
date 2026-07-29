from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.clinical_document import ClinicalDocumentSummaryResponse
from app.schemas.medication import MedicationResponse


class DiscrepancyType(str, Enum):
    MISSING_FROM_MEDICATION_LIST = "missing_from_medication_list"
    DISCONTINUED_STATUS_CONFLICT = "discontinued_status_conflict"
    DOSE_CONFLICT = "dose_conflict"
    ROUTE_CONFLICT = "route_conflict"
    FREQUENCY_CONFLICT = "frequency_conflict"
    STATUS_CONFLICT = "status_conflict"
    UNSUPPORTED_MEDICATION_LIST_ENTRY = "unsupported_medication_list_entry"


class DiscrepancySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResolutionStatus(str, Enum):
    OPEN = "open"
    REVIEWED = "reviewed"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class MedicationDiscrepancyCreate(BaseModel):
    medication_id: int | None = None
    medication_mention_id: int | None = None

    discrepancy_type: DiscrepancyType
    severity: DiscrepancySeverity

    title: str = Field(min_length=1)
    ai_explanation: str | None = None
    recommendation: str | None = None

    expected_value: str | None = None
    observed_value: str | None = None

    resolution_status: ResolutionStatus = ResolutionStatus.OPEN


class MedicationDiscrepancyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    analysis_id: int
    medication_id: int | None
    medication_mention_id: int | None

    discrepancy_type: DiscrepancyType
    severity: DiscrepancySeverity

    title: str
    ai_explanation: str | None
    recommendation: str | None

    expected_value: str | None
    observed_value: str | None

    resolution_status: ResolutionStatus

    created_at: datetime
    updated_at: datetime | None


class MedicationMentionEvidenceResponse(BaseModel):
    """A MedicationMention as supporting evidence for a discrepancy.

    MedicationMention has no API exposure of its own elsewhere in the app -
    this is a purpose-built, read-only view of it for this one use, not a
    general-purpose mention schema.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    medication_name: str
    dose: str | None
    route: str | None
    frequency: str | None
    status: str | None
    context_text: str | None
    clinical_document: ClinicalDocumentSummaryResponse


class MedicationDiscrepancyDetailResponse(MedicationDiscrepancyResponse):
    """MedicationDiscrepancyResponse plus the supporting evidence a provider
    needs to evaluate the finding, without a separate request: the patient's
    own Medication row (when medication_id is set) and/or the MedicationMention
    that was actually extracted from a clinical document (when
    medication_mention_id is set). Either, both, or neither may be present,
    matching the nullability of the two source foreign keys.
    """

    medication: MedicationResponse | None = None
    medication_mention: MedicationMentionEvidenceResponse | None = None
