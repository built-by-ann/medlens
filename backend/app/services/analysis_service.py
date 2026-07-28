from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from app.models.analysis import Analysis
from app.models.clinical_document import ClinicalDocument
from app.schemas.analysis import AnalysisCompletedSummary, AnalysisCreate


class InvalidClinicalDocumentIdsError(Exception):
    def __init__(self, invalid_ids: list[int]):
        self.invalid_ids = invalid_ids
        super().__init__(f"Invalid or inaccessible clinical document ids: {invalid_ids}")


def create_analysis(db: Session, user_id: int, analysis_in: AnalysisCreate) -> Analysis:
    requested_ids = set(analysis_in.clinical_document_ids)

    documents = (
        db.query(ClinicalDocument)
        .filter(
            ClinicalDocument.id.in_(requested_ids),
            ClinicalDocument.user_id == user_id,
        )
        .all()
    )

    found_ids = {document.id for document in documents}
    missing_ids = requested_ids - found_ids

    # A missing id may be nonexistent or owned by another user. Both cases
    # raise the same error so a caller cannot use this to probe whether a
    # given id belongs to someone else.
    if missing_ids:
        raise InvalidClinicalDocumentIdsError(sorted(missing_ids))

    analysis = Analysis(
        user_id=user_id,
        status="pending",
        clinical_documents=documents,
    )

    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return analysis


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


def get_analysis_for_user(db: Session, user_id: int, analysis_id: int) -> Analysis | None:
    # selectinload avoids N+1 queries for the two child collections, and
    # avoids the cartesian product joinedload would produce when eagerly
    # loading two independent one-to-many relationships at once. Ordering
    # of these collections is decided by the caller, not here, so this
    # function never mutates the loaded relationship collections.
    return (
        db.query(Analysis)
        .options(
            selectinload(Analysis.medication_mentions),
            selectinload(Analysis.possible_inconsistencies),
        )
        .filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user_id,
        )
        .first()
    )


def delete_analysis(db: Session, user_id: int, analysis_id: int) -> bool:
    analysis = get_analysis_for_user(db, user_id, analysis_id)

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
