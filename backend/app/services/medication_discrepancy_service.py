from sqlalchemy.orm import Session

from app.models.medication_discrepancy import MedicationDiscrepancy
from app.schemas.medication_discrepancy import MedicationDiscrepancyCreate


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
