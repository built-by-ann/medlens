from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.ai.providers.base import AIProviderError
from app.ai.schemas import ClinicalNoteSummaryRequest, ClinicalNoteSummaryResponse
from app.ai.service import AISummaryService, get_ai_summary_service
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.analysis import AnalysisCreate, AnalysisDetailResponse, AnalysisSummaryResponse
from app.services.analysis_result_service import persist_analysis_result
from app.services.analysis_service import (
    InvalidClinicalDocumentIdsError,
    create_analysis,
    delete_analysis,
    get_analysis_for_user,
    list_analyses_for_user,
    mark_analysis_failed,
    mark_analysis_processing,
)

router = APIRouter(prefix="/ai", tags=["ai"])

NOT_FOUND_DETAIL = "Clinical document not found"
ANALYSIS_NOT_FOUND_DETAIL = "Analysis not found"


def _safe_error_message(error: Exception) -> str:
    if isinstance(error, AIProviderError):
        return str(error)

    return f"Analysis failed due to an internal error ({type(error).__name__})."


@router.post(
    "/summarize",
    response_model=ClinicalNoteSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def summarize_clinical_documents(
    request: ClinicalNoteSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ai_summary_service: AISummaryService = Depends(get_ai_summary_service),
) -> ClinicalNoteSummaryResponse:
    try:
        analysis = create_analysis(
            db,
            current_user.id,
            AnalysisCreate(clinical_document_ids=request.clinical_document_ids),
        )
    except InvalidClinicalDocumentIdsError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    try:
        mark_analysis_processing(db, analysis)

        clinical_notes = [document.raw_text for document in analysis.clinical_documents]
        result = ai_summary_service.summarize(clinical_notes)

        persist_analysis_result(
            db,
            analysis,
            result.clinical_summary,
            provider=result.provider,
            model=result.model,
        )
    except Exception as error:
        db.rollback()
        message = _safe_error_message(error)
        mark_analysis_failed(db, analysis, message)

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=message,
        )

    return ClinicalNoteSummaryResponse(
        analysis_id=analysis.id,
        provider=result.provider,
        model=result.model,
        **result.clinical_summary.model_dump(),
    )


@router.get("/analyses", response_model=list[AnalysisSummaryResponse])
def list_analyses(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[AnalysisSummaryResponse]:
    analyses = list_analyses_for_user(db, current_user.id, limit=limit)

    return [
        AnalysisSummaryResponse(
            id=analysis.id,
            status=analysis.status,
            created_at=analysis.created_at,
            completed_at=analysis.completed_at,
            error_message=analysis.error_message,
            summary=analysis.summary,
            document_count=len(analysis.clinical_documents),
            total_findings=analysis.total_findings,
            high_severity_findings=analysis.high_severity_findings,
            medium_severity_findings=analysis.medium_severity_findings,
            low_severity_findings=analysis.low_severity_findings,
            provider=analysis.provider,
            model_name=analysis.model_name,
        )
        for analysis in analyses
    ]


@router.get("/analyses/{analysis_id}", response_model=AnalysisDetailResponse)
def get_analysis_detail(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AnalysisDetailResponse:
    analysis = get_analysis_for_user(db, current_user.id, analysis_id)

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ANALYSIS_NOT_FOUND_DETAIL,
        )

    # Rows created in the same persistence transaction can share an
    # identical created_at (Postgres's now() is constant within a
    # transaction), so id is the only reliably deterministic sort key here.
    # sorted() builds new lists rather than mutating analysis.medication_mentions
    # / analysis.possible_inconsistencies in place, so the ORM-managed
    # relationship collections on `analysis` are left untouched.
    return AnalysisDetailResponse(
        id=analysis.id,
        status=analysis.status,
        provider=analysis.provider,
        model_name=analysis.model_name,
        summary=analysis.summary,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        error_message=analysis.error_message,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
        medication_mentions=sorted(analysis.medication_mentions, key=lambda mention: mention.id),
        possible_inconsistencies=sorted(
            analysis.possible_inconsistencies, key=lambda inconsistency: inconsistency.id
        ),
    )


@router.delete("/analyses/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis_detail(
    analysis_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    deleted = delete_analysis(db, current_user.id, analysis_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ANALYSIS_NOT_FOUND_DETAIL,
        )
