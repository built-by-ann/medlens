from sqlalchemy.orm import Session

from app.models.medication_discrepancy import MedicationDiscrepancy
from app.schemas.medication_discrepancy import MedicationDiscrepancyCreate


def create_medication_discrepancy(
    db: Session, analysis_id: int, discrepancy_in: MedicationDiscrepancyCreate
) -> MedicationDiscrepancy:
    discrepancy = MedicationDiscrepancy(
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

    db.add(discrepancy)
    db.commit()
    db.refresh(discrepancy)

    return discrepancy
