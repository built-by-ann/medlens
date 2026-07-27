from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.providers.base import AIProviderError
from app.ai.schemas import ClinicalNoteSummaryRequest, ClinicalNoteSummaryResponse
from app.ai.service import AISummaryService, get_ai_summary_service
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.analysis import AnalysisCreate
from app.services.analysis_result_service import persist_analysis_result
from app.services.analysis_service import (
    InvalidClinicalDocumentIdsError,
    create_analysis,
    mark_analysis_failed,
    mark_analysis_processing,
)

router = APIRouter(prefix="/ai", tags=["ai"])

NOT_FOUND_DETAIL = "Clinical document not found"


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
