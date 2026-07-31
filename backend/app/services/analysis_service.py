from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.models.analysis import Analysis
from app.models.clinical_document import ClinicalDocument
from app.models.medication_discrepancy import MedicationDiscrepancy
from app.models.medication_mention import MedicationMention
from app.models.patient import Patient
from app.schemas.analysis import AnalysisCompletedSummary, AnalysisCreate
from app.services.patient_service import ARCHIVED_STATUS


class InvalidClinicalDocumentIdsError(Exception):
    def __init__(self, invalid_ids: list[int]):
        self.invalid_ids = invalid_ids
        super().__init__(f"Invalid or inaccessible clinical document ids: {invalid_ids}")


def create_analysis(db: Session, patient: Patient, analysis_in: AnalysisCreate) -> Analysis:
    requested_ids = set(analysis_in.clinical_document_ids)

    documents = (
        db.query(ClinicalDocument)
        .filter(
            ClinicalDocument.id.in_(requested_ids),
            ClinicalDocument.patient_id == patient.id,
        )
        .all()
    )

    found_ids = {document.id for document in documents}
    missing_ids = requested_ids - found_ids

    # A missing id may be nonexistent, owned by a different patient
    # (including a different patient owned by the same user), or owned by
    # a different user entirely. All three raise the same error so a
    # caller cannot use this to probe whether a given id belongs to
    # someone else, or to some other patient of theirs.
    if missing_ids:
        raise InvalidClinicalDocumentIdsError(sorted(missing_ids))

    analysis = Analysis(
        patient_id=patient.id,
        status="pending",
        clinical_documents=documents,
    )

    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return analysis


def ordered_clinical_documents(analysis: Analysis) -> list[ClinicalDocument]:
    """A deterministic order for `analysis.clinical_documents`.

    It's a plain many-to-many relationship (see analysis_clinical_documents
    in docs/data-model.md) with no inherent ordering guarantee - the rows
    SQLAlchemy returns aren't reliably insertion order or id order. This
    matters as of Issue #152: the AI prompt numbers each document it is
    given ("Note 1", "Note 2", ...; see app/ai/prompts.py), and the AI's
    response reports which numbered note a given medication came from, so
    that numbering has to be reproducible - the same order used to build
    the prompt (app/api/routes/analyses.py) must be the same order used
    afterward to map a reported note number back to a real document id
    (medication_reconciliation_service.py). Sorting by id ascending is that
    one canonical order, used by both call sites instead of each re-deriving
    (and risking disagreeing about) their own.
    """
    return sorted(analysis.clinical_documents, key=lambda document: document.id)


def mark_analysis_processing(db: Session, analysis: Analysis) -> Analysis:
    analysis.status = "processing"
    analysis.started_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(analysis)

    return analysis


def mark_analysis_completed(
    db: Session, analysis: Analysis, summary_in: AnalysisCompletedSummary
) -> Analysis:
    analysis.status = "completed"
    analysis.completed_at = datetime.now(timezone.utc)
    analysis.error_message = None

    analysis.summary = summary_in.summary
    analysis.total_findings = summary_in.total_findings
    analysis.high_severity_findings = summary_in.high_severity_findings
    analysis.medium_severity_findings = summary_in.medium_severity_findings
    analysis.low_severity_findings = summary_in.low_severity_findings
    analysis.provider = summary_in.provider
    analysis.model_name = summary_in.model_name

    db.commit()
    db.refresh(analysis)

    return analysis


def get_analysis_for_patient(db: Session, patient_id: int, analysis_id: int) -> Analysis | None:
    # selectinload avoids N+1 queries for each child collection, and avoids
    # the cartesian product joinedload would produce when eagerly loading
    # several independent one-to-many relationships at once. Ordering of
    # these collections is decided by the caller, not here, so this
    # function never mutates the loaded relationship collections.
    return (
        db.query(Analysis)
        .options(
            selectinload(Analysis.medication_mentions),
            selectinload(Analysis.possible_inconsistencies),
            selectinload(Analysis.medication_discrepancies).selectinload(
                MedicationDiscrepancy.medication
            ),
            selectinload(Analysis.medication_discrepancies)
            .selectinload(MedicationDiscrepancy.medication_mention)
            .selectinload(MedicationMention.clinical_document),
            # Issue #47: needed for the document_count property below.
            selectinload(Analysis.clinical_documents),
        )
        .filter(
            Analysis.id == analysis_id,
            Analysis.patient_id == patient_id,
        )
        .first()
    )


def list_analyses_for_patient(db: Session, patient_id: int, limit: int) -> list[Analysis]:
    # id descending, not created_at, for the same reason documented on
    # get_analysis_for_patient's sibling callers elsewhere in this codebase:
    # Postgres's now() is constant within a transaction, so created_at is
    # not guaranteed to break ties between rows persisted together.
    # selectinload avoids an N+1 query for clinical_documents (needed to
    # compute each row's document count) across the whole page of results.
    return (
        db.query(Analysis)
        .options(selectinload(Analysis.clinical_documents))
        .filter(Analysis.patient_id == patient_id)
        .order_by(Analysis.id.desc())
        .limit(limit)
        .all()
    )


def list_recent_analyses_for_user(db: Session, user_id: int, limit: int) -> list[Analysis]:
    # Issue #157: the Dashboard's Recent Analyses feed, the one place an
    # analysis is shown across every patient a user owns rather than one
    # patient's own pages. Joins to Patient purely to scope by user_id and
    # exclude archived patients (the same exclusion list_patients already
    # applies) - selectinload still eager-loads the patient relationship so
    # the route can read analysis.patient.first_name/last_name with no
    # further query.
    return (
        db.query(Analysis)
        .join(Patient, Analysis.patient_id == Patient.id)
        .options(selectinload(Analysis.patient))
        .filter(
            Patient.user_id == user_id,
            Patient.status != ARCHIVED_STATUS,
        )
        .order_by(Analysis.id.desc())
        .limit(limit)
        .all()
    )


def delete_analysis(db: Session, patient_id: int, analysis_id: int) -> bool:
    analysis = get_analysis_for_patient(db, patient_id, analysis_id)

    if analysis is None:
        return False

    # medication_discrepancies, medication_mentions, and possible_inconsistencies
    # are all configured with cascade="all, delete-orphan" on this relationship,
    # so deleting the Analysis instance is enough for SQLAlchemy to delete every
    # analysis-scoped child row. clinical_documents is a plain many-to-many
    # relationship with no such cascade, so the linked ClinicalDocument rows are
    # left untouched; only the association table rows are removed, via the
    # ON DELETE CASCADE already defined on analysis_clinical_documents.
    db.delete(analysis)
    db.commit()

    return True


def mark_analysis_failed(db: Session, analysis: Analysis, error_message: str) -> Analysis:
    analysis.status = "failed"
    analysis.completed_at = datetime.now(timezone.utc)
    analysis.error_message = error_message

    analysis.total_findings = 0
    analysis.high_severity_findings = 0
    analysis.medium_severity_findings = 0
    analysis.low_severity_findings = 0

    db.commit()
    db.refresh(analysis)

    return analysis
