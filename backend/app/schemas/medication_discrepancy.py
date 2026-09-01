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


class ResolutionAction(str, Enum):
    """What a provider actually did to resolve a discrepancy, distinct from
    ResolutionStatus (the coarser open/resolved/dismissed state that
    results), this is the specific operation, recorded for the audit trail.
    Which actions are valid for a given discrepancy depends on its
    DiscrepancyType, enforced in resolve_discrepancy
    (medication_discrepancy_service.py), not by this enum alone.
    """

    # Only valid when medication_id is None (nothing to update yet) -
    # creates a new Medication from the fields in DiscrepancyResolutionIn.
    ADD_MEDICATION = "add_medication"
    # Only valid when medication_id is set; updates that Medication with
    # whichever fields are present in DiscrepancyResolutionIn (the frontend
    # decides whether those were auto-suggested from the discrepancy's own
    # evidence or manually typed; the backend treats both identically).
    UPDATE_MEDICATION = "update_medication"
    # Valid for any discrepancy type. Never touches a Medication row.
    DISMISS = "dismiss"


class DiscrepancyResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ResolutionAction
    medication_name: str | None = Field(default=None, min_length=1)
    dose: str | None = Field(default=None, min_length=1)
    route: str | None = Field(default=None, min_length=1)
    frequency: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1)
    # Provider's own free-text rationale, independent of any medication
    # field, always optional, never required to resolve a discrepancy.
    note: str | None = Field(default=None, min_length=1)


class ResolvedByResponse(BaseModel):
    """Who resolved a discrepancy, a minimal, purpose-built view of User
    for this one nested use (mirrors MedicationMentionEvidenceResponse
    below), not a general-purpose user schema.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None
    username: str | None
    email: str


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
    resolution_action: ResolutionAction | None
    resolved_at: datetime | None
    resolution_note: str | None

    created_at: datetime
    updated_at: datetime | None


class MedicationMentionEvidenceResponse(BaseModel):
    """A MedicationMention as supporting evidence for a discrepancy (Issue #46).

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
    that was actually extracted (when medication_mention_id is set). Either,
    both, or neither may be present, matching the nullability of the two
    source foreign keys (both ON DELETE SET NULL).
    """

    medication: MedicationResponse | None = None
    medication_mention: MedicationMentionEvidenceResponse | None = None
    resolved_by: ResolvedByResponse | None = None
