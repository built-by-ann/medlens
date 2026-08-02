from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.medication_discrepancy import MedicationDiscrepancy
from app.models.patient import Patient
from app.models.user import User
from app.schemas.medication import MedicationCreate, MedicationUpdate
from app.schemas.medication_discrepancy import (
    DiscrepancyResolutionIn,
    DiscrepancyType,
    MedicationDiscrepancyCreate,
    ResolutionAction,
    ResolutionStatus,
)
from app.services.medication_service import create_medication, update_medication

# discrepancy_type values (see DiscrepancyType) for which "add_medication"
# makes sense - only when there is genuinely no Medication row yet.
_ADD_ELIGIBLE_TYPES = {DiscrepancyType.MISSING_FROM_MEDICATION_LIST}

# Every other type has a Medication row already (medication_id is set) - the
# resolution is updating it, not creating a new one. This includes
# unsupported_medication_list_entry: there's no mention to add *from*, but a
# provider can still hand-correct the existing Medication ("edit manually").
_UPDATE_ELIGIBLE_TYPES = {
    DiscrepancyType.DISCONTINUED_STATUS_CONFLICT,
    DiscrepancyType.DOSE_CONFLICT,
    DiscrepancyType.ROUTE_CONFLICT,
    DiscrepancyType.FREQUENCY_CONFLICT,
    DiscrepancyType.STATUS_CONFLICT,
    DiscrepancyType.UNSUPPORTED_MEDICATION_LIST_ENTRY,
}


class InvalidResolutionActionError(Exception):
    """Raised when the requested action doesn't make sense for this specific
    discrepancy - either the wrong action for its discrepancy_type, or
    (defensively) a medication_id/mention state that shouldn't be possible
    given that type. The route layer turns this into a 400.
    """


class DiscrepancyAlreadyResolvedError(Exception):
    """Raised when resolving a discrepancy whose resolution_status is no
    longer "open" - resolving is one-way; there is no "re-open" action, so a
    second resolve attempt is always a conflict, not an update. The route
    layer turns this into a 409.
    """


def _build_medication_discrepancy(
    analysis_id: int, discrepancy_in: MedicationDiscrepancyCreate
) -> MedicationDiscrepancy:
    return MedicationDiscrepancy(
        analysis_id=analysis_id,
        medication_id=discrepancy_in.medication_id,
        medication_mention_id=discrepancy_in.medication_mention_id,
        discrepancy_type=discrepancy_in.discrepancy_type.value,
        severity=discrepancy_in.severity.value,
        title=discrepancy_in.title,
        ai_explanation=discrepancy_in.ai_explanation,
        recommendation=discrepancy_in.recommendation,
        expected_value=discrepancy_in.expected_value,
        observed_value=discrepancy_in.observed_value,
        resolution_status=discrepancy_in.resolution_status.value,
    )


def create_medication_discrepancy(
    db: Session, analysis_id: int, discrepancy_in: MedicationDiscrepancyCreate
) -> MedicationDiscrepancy:
    discrepancy = _build_medication_discrepancy(analysis_id, discrepancy_in)

    db.add(discrepancy)
    db.commit()
    db.refresh(discrepancy)

    return discrepancy


def create_medication_discrepancies(
    db: Session, analysis_id: int, discrepancies_in: list[MedicationDiscrepancyCreate]
) -> list[MedicationDiscrepancy]:
    # Does not commit. Callers that need to persist these discrepancies as part
    # of a larger transaction (for example, alongside an Analysis completion
    # update) are responsible for committing once everything is staged.
    discrepancies = [
        _build_medication_discrepancy(analysis_id, discrepancy_in)
        for discrepancy_in in discrepancies_in
    ]

    db.add_all(discrepancies)

    return discrepancies


def get_discrepancy_for_analysis(
    db: Session, analysis_id: int, discrepancy_id: int
) -> MedicationDiscrepancy | None:
    return (
        db.query(MedicationDiscrepancy)
        .filter(
            MedicationDiscrepancy.id == discrepancy_id,
            MedicationDiscrepancy.analysis_id == analysis_id,
        )
        .first()
    )


def resolve_discrepancy(
    db: Session,
    discrepancy: MedicationDiscrepancy,
    patient: Patient,
    resolution_in: DiscrepancyResolutionIn,
    resolved_by: User,
) -> MedicationDiscrepancy:
    """Applies a provider's resolution to one discrepancy: for an accept
    action, creates or updates the relevant Medication (reusing
    medication_service's own create_medication/update_medication - this
    function never builds or writes a Medication row itself, so there is
    exactly one place medication mutation logic lives); for dismiss, no
    Medication is touched at all. Either way, records who/when/what/why on
    the discrepancy itself - the audit trail - and leaves every field the
    original reconciliation run computed (title, ai_explanation,
    expected_value, observed_value, ...) untouched, so the record of what
    was originally found is never lost, only added to.

    Raises DiscrepancyAlreadyResolvedError if resolution_status isn't
    "open" (resolving is one-way - there is no un-resolve), and
    InvalidResolutionActionError if the action doesn't fit this
    discrepancy's type or current medication linkage. Callers commit; this
    function only adds/stages changes, matching create_medication_discrepancies'
    existing convention of leaving transaction boundaries to the route.
    """
    if discrepancy.resolution_status != ResolutionStatus.OPEN.value:
        raise DiscrepancyAlreadyResolvedError(
            f"Discrepancy {discrepancy.id} has already been {discrepancy.resolution_status}"
        )

    discrepancy_type = DiscrepancyType(discrepancy.discrepancy_type)

    if resolution_in.action == ResolutionAction.DISMISS:
        pass  # No medication is ever touched by a dismissal.
    elif resolution_in.action == ResolutionAction.ADD_MEDICATION:
        if discrepancy_type not in _ADD_ELIGIBLE_TYPES:
            raise InvalidResolutionActionError(
                "add_medication is only valid for a medication missing from the list"
            )
        if discrepancy.medication_id is not None:
            raise InvalidResolutionActionError("This discrepancy is already linked to a medication")
        if not all(
            [
                resolution_in.medication_name,
                resolution_in.dose,
                resolution_in.route,
                resolution_in.frequency,
                resolution_in.status,
            ]
        ):
            raise InvalidResolutionActionError(
                "medication_name, dose, route, frequency, and status are all "
                "required to add a medication"
            )

        medication = create_medication(
            db,
            patient,
            MedicationCreate(
                medication_name=resolution_in.medication_name,
                dose=resolution_in.dose,
                route=resolution_in.route,
                frequency=resolution_in.frequency,
                status=resolution_in.status,
                # Distinguishes reconciliation-created medications from ones
                # entered directly (source="patient_reported") or imported
                # via CSV - source is a freeform string (app/schemas/medication.py),
                # so this is a project convention, not an enforced enum.
                source="reconciliation",
            ),
        )
        # Cross-references the discrepancy to the medication it produced,
        # completing the audit trail ("this finding resulted in this row").
        discrepancy.medication_id = medication.id
    elif resolution_in.action == ResolutionAction.UPDATE_MEDICATION:
        if discrepancy_type not in _UPDATE_ELIGIBLE_TYPES:
            raise InvalidResolutionActionError(
                "update_medication is not valid for this discrepancy type"
            )
        if discrepancy.medication_id is None:
            raise InvalidResolutionActionError(
                "This discrepancy has no associated medication to update"
            )

        update_fields = resolution_in.model_dump(
            include={"medication_name", "dose", "route", "frequency", "status"},
            exclude_none=True,
        )
        if not update_fields:
            raise InvalidResolutionActionError(
                "At least one medication field must be provided to update_medication"
            )

        updated_medication = update_medication(
            db, patient.id, discrepancy.medication_id, MedicationUpdate(**update_fields)
        )
        # update_medication scopes its lookup by patient_id (app/services/medication_service.py)
        # and returns None rather than raising if nothing matched - defensively
        # checked here since silently marking the discrepancy resolved while
        # actually changing nothing would be a worse failure than a clear 400.
        if updated_medication is None:
            raise InvalidResolutionActionError(
                "The medication linked to this discrepancy no longer belongs to this patient"
            )
    else:
        raise InvalidResolutionActionError(f"Unknown resolution action: {resolution_in.action}")

    discrepancy.resolution_status = (
        ResolutionStatus.DISMISSED.value
        if resolution_in.action == ResolutionAction.DISMISS
        else ResolutionStatus.RESOLVED.value
    )
    discrepancy.resolution_action = resolution_in.action.value
    discrepancy.resolved_by_user_id = resolved_by.id
    discrepancy.resolved_at = datetime.now(UTC)
    discrepancy.resolution_note = resolution_in.note

    db.add(discrepancy)

    return discrepancy
