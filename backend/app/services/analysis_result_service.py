from sqlalchemy.orm import Session

from app.ai.schemas import ClinicalSummary
from app.models.analysis import Analysis
from app.models.analysis_inconsistency import AnalysisInconsistency
from app.models.analysis_medication_mention import AnalysisMedicationMention
from app.schemas.analysis import AnalysisCompletedSummary
from app.services.analysis_service import mark_analysis_completed


def persist_analysis_result(
    db: Session,
    analysis: Analysis,
    clinical_summary: ClinicalSummary,
    provider: str,
    model: str,
) -> Analysis:
    """Persist a validated ClinicalSummary as the completed result of an analysis.

    Medication mentions and inconsistencies are staged with db.add() but not
    committed here. mark_analysis_completed's own commit persists everything
    staged in the session together, so either all of it is saved (the
    mentions, the inconsistencies, and the completed Analysis fields) or, if
    an exception is raised before that commit, the caller can roll back and
    none of it is.

    No reconciliation happens here. total_findings and the severity counts
    are set to zero, since no MedicationDiscrepancy rows are created by this
    function.
    """
    for medication in clinical_summary.medications:
        db.add(
            AnalysisMedicationMention(
                analysis_id=analysis.id,
                medication_name=medication.name,
                dosage=medication.dosage,
                route=medication.route,
                frequency=medication.frequency,
                status=medication.status,
                notes=medication.notes,
            )
        )

    for description in clinical_summary.possible_inconsistencies:
        db.add(
            AnalysisInconsistency(
                analysis_id=analysis.id,
                description=description,
            )
        )

    summary_in = AnalysisCompletedSummary(
        summary=clinical_summary.summary,
        total_findings=0,
        high_severity_findings=0,
        medium_severity_findings=0,
        low_severity_findings=0,
        provider=provider,
        model_name=model,
    )

    return mark_analysis_completed(db, analysis, summary_in)
