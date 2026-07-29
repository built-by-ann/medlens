from sqlalchemy.orm import Session

from app.ai.schemas import ClinicalSummary
from app.models.analysis import Analysis
from app.models.analysis_inconsistency import AnalysisInconsistency
from app.models.analysis_medication_mention import AnalysisMedicationMention
from app.schemas.analysis import AnalysisCompletedSummary
from app.services.analysis_service import mark_analysis_completed
from app.services.medication_reconciliation_service import reconcile_ai_extracted_medications


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
    mentions, the inconsistencies, the reconciliation findings below, and
    the completed Analysis fields) or, if an exception is raised before that
    commit (including one raised by reconciliation itself), the caller's
    surrounding try/except rolls back and none of it is - see
    app/api/routes/analyses.py.

    As of Issue #148, medication reconciliation runs here too, immediately
    after the AI-extracted medications are known: reconcile_ai_extracted_medications
    persists them as real MedicationMention rows and runs the existing
    reconciliation engine against the patient's medication list, producing
    real MedicationDiscrepancy rows and severity counts - rather than the
    hardcoded zeros this function used before that engine was wired in. See
    docs/architecture.md for the full pipeline.
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

    counts = reconcile_ai_extracted_medications(db, analysis, clinical_summary.medications)

    summary_in = AnalysisCompletedSummary(
        summary=clinical_summary.summary,
        total_findings=counts["total"],
        high_severity_findings=counts["high"],
        medium_severity_findings=counts["medium"],
        low_severity_findings=counts["low"],
        provider=provider,
        model_name=model,
    )

    return mark_analysis_completed(db, analysis, summary_in)
