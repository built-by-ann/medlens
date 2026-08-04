import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.ai.providers.base import AIProviderError
from app.ai.schemas import ClinicalNoteSummaryRequest, ClinicalNoteSummaryResponse
from app.ai.service import AISummaryService, get_ai_summary_service
from app.api.deps import get_current_user, get_owned_patient
from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.patient import Patient
from app.models.user import User
from app.schemas.analysis import (
    AnalysisCreate,
    AnalysisDetailResponse,
    AnalysisSummaryResponse,
    RecentAnalysisResponse,
)
from app.schemas.medication_discrepancy import (
    DiscrepancyResolutionIn,
    MedicationDiscrepancyDetailResponse,
)
from app.schemas.patient import PatientSummaryResponse
from app.services.analysis_result_service import persist_analysis_result
from app.services.analysis_service import (
    InvalidClinicalDocumentIdsError,
    create_analysis,
    delete_analysis,
    get_analysis_for_patient,
    list_analyses_for_patient,
    list_recent_analyses_for_user,
    mark_analysis_failed,
    mark_analysis_processing,
    ordered_clinical_documents,
)
from app.services.medication_discrepancy_service import (
    DiscrepancyAlreadyResolvedError,
    InvalidResolutionActionError,
    get_discrepancy_for_analysis,
    resolve_discrepancy,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patients/{patient_id}/analyses", tags=["analyses"])

# Cross-patient, unlike `router` above - the Dashboard's Recent Analyses
# feed (Issue #157) spans every patient a user owns, so it can't be nested
# under a single patient_id the way every other analyses route is.
recent_analyses_router = APIRouter(prefix="/analyses", tags=["analyses"])

NOT_FOUND_DETAIL = "Clinical document not found"
ANALYSIS_NOT_FOUND_DETAIL = "Analysis not found"
DISCREPANCY_NOT_FOUND_DETAIL = "Discrepancy not found"


def _safe_error_message(error: Exception) -> str:
    if isinstance(error, AIProviderError):
        return str(error)

    return f"Analysis failed due to an internal error ({type(error).__name__})."


def _count_open_findings(analysis: Analysis) -> int:
    return sum(
        1
        for discrepancy in analysis.medication_discrepancies
        if discrepancy.resolution_status == "open"
    )


@router.post(
    "",
    response_model=ClinicalNoteSummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
def summarize_clinical_documents(
    request: ClinicalNoteSummaryRequest,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
    ai_summary_service: AISummaryService = Depends(get_ai_summary_service),
) -> ClinicalNoteSummaryResponse:
    try:
        analysis = create_analysis(
            db,
            patient,
            AnalysisCreate(clinical_document_ids=request.clinical_document_ids),
        )
    except InvalidClinicalDocumentIdsError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        ) from None

    logger.info(
        "Analysis started",
        extra={
            "event": "analysis_started",
            "patient_id": patient.id,
            "analysis_id": analysis.id,
        },
    )

    started_at = time.monotonic()

    try:
        mark_analysis_processing(db, analysis)

        # ordered_clinical_documents fixes the "Note N" numbering the prompt
        # uses (app/ai/prompts.py) to a reproducible order - the same order
        # reconcile_ai_extracted_medications uses afterward to map each
        # medication's reported source note back to a real document id
        # (Issue #152).
        clinical_notes = [document.raw_text for document in ordered_clinical_documents(analysis)]
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
        duration_ms = (time.monotonic() - started_at) * 1000

        # message is already sanitized by _safe_error_message - the same
        # text returned to the client in the 503 below, never a raw
        # exception message or traceback (that's logger.exception's job,
        # already covered by GeminiProvider._log_failure for the AI-provider
        # case, or by the global exception handler for anything else - see
        # app/core/logging_config.py). This log's job is only to record
        # *that*, and *which*, analysis failed and why in the sanitized,
        # already-safe terms a client would also see.
        logger.warning(
            "Analysis failed: %s",
            message,
            extra={
                "event": "analysis_failed",
                "patient_id": patient.id,
                "analysis_id": analysis.id,
                "duration_ms": round(duration_ms, 1),
            },
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=message,
        ) from error

    duration_ms = (time.monotonic() - started_at) * 1000

    # duration_ms here is the whole pipeline this route runs after marking
    # the analysis processing - AI request (already timed on its own by
    # GeminiProvider, app/ai/providers/gemini_provider.py) plus response
    # validation and reconciliation (persist_analysis_result, above) - not
    # a duplicate of the AI provider's own timing, a broader span that
    # includes it.
    logger.info(
        "Analysis completed",
        extra={
            "event": "analysis_completed",
            "patient_id": patient.id,
            "analysis_id": analysis.id,
            "provider": result.provider,
            "model": result.model,
            "duration_ms": round(duration_ms, 1),
        },
    )

    return ClinicalNoteSummaryResponse(
        analysis_id=analysis.id,
        provider=result.provider,
        model=result.model,
        **result.clinical_summary.model_dump(),
    )


@router.get("", response_model=list[AnalysisSummaryResponse])
def list_analyses(
    limit: int = Query(default=10, ge=1, le=50),
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> list[AnalysisSummaryResponse]:
    analyses = list_analyses_for_patient(db, patient.id, limit=limit)

    return [
        AnalysisSummaryResponse(
            id=analysis.id,
            patient_id=analysis.patient_id,
            status=analysis.status,
            created_at=analysis.created_at,
            completed_at=analysis.completed_at,
            error_message=analysis.error_message,
            summary=analysis.summary,
            document_count=analysis.document_count,
            total_findings=analysis.total_findings,
            high_severity_findings=analysis.high_severity_findings,
            medium_severity_findings=analysis.medium_severity_findings,
            low_severity_findings=analysis.low_severity_findings,
            open_findings=_count_open_findings(analysis),
            provider=analysis.provider,
            model_name=analysis.model_name,
        )
        for analysis in analyses
    ]


@router.get("/{analysis_id}", response_model=AnalysisDetailResponse)
def get_analysis_detail(
    analysis_id: int,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> AnalysisDetailResponse:
    analysis = get_analysis_for_patient(db, patient.id, analysis_id)

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ANALYSIS_NOT_FOUND_DETAIL,
        )

    # Rows created in the same persistence transaction can share an
    # identical created_at (Postgres's now() is constant within a
    # transaction), so id is the only reliably deterministic sort key here.
    # sorted() builds new lists rather than mutating analysis.medication_mentions
    # / analysis.possible_inconsistencies / analysis.medication_discrepancies in
    # place, so the ORM-managed relationship collections on `analysis` are
    # left untouched.
    return AnalysisDetailResponse(
        id=analysis.id,
        patient_id=analysis.patient_id,
        status=analysis.status,
        provider=analysis.provider,
        model_name=analysis.model_name,
        summary=analysis.summary,
        started_at=analysis.started_at,
        completed_at=analysis.completed_at,
        error_message=analysis.error_message,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
        document_count=analysis.document_count,
        medication_mentions=sorted(analysis.medication_mentions, key=lambda mention: mention.id),
        possible_inconsistencies=sorted(
            analysis.possible_inconsistencies, key=lambda inconsistency: inconsistency.id
        ),
        medication_discrepancies=sorted(
            analysis.medication_discrepancies, key=lambda discrepancy: discrepancy.id
        ),
    )


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis_detail(
    analysis_id: int,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> None:
    deleted = delete_analysis(db, patient.id, analysis_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ANALYSIS_NOT_FOUND_DETAIL,
        )


@router.post(
    "/{analysis_id}/discrepancies/{discrepancy_id}/resolve",
    response_model=MedicationDiscrepancyDetailResponse,
    summary="Resolve discrepancy",
)
def resolve_discrepancy_route(
    analysis_id: int,
    discrepancy_id: int,
    resolution_in: DiscrepancyResolutionIn,
    patient: Patient = Depends(get_owned_patient),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MedicationDiscrepancyDetailResponse:
    analysis = get_analysis_for_patient(db, patient.id, analysis_id)

    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ANALYSIS_NOT_FOUND_DETAIL,
        )

    discrepancy = get_discrepancy_for_analysis(db, analysis.id, discrepancy_id)

    if discrepancy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=DISCREPANCY_NOT_FOUND_DETAIL,
        )

    try:
        resolved = resolve_discrepancy(db, discrepancy, patient, resolution_in, current_user)
    except DiscrepancyAlreadyResolvedError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    except InvalidResolutionActionError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from None

    db.commit()
    db.refresh(resolved)

    return resolved


@recent_analyses_router.get("/recent", response_model=list[RecentAnalysisResponse])
def list_recent_analyses(
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecentAnalysisResponse]:
    analyses = list_recent_analyses_for_user(db, current_user.id, limit=limit)

    return [
        RecentAnalysisResponse(
            id=analysis.id,
            patient_id=analysis.patient_id,
            status=analysis.status,
            created_at=analysis.created_at,
            completed_at=analysis.completed_at,
            error_message=analysis.error_message,
            summary=analysis.summary,
            document_count=analysis.document_count,
            total_findings=analysis.total_findings,
            high_severity_findings=analysis.high_severity_findings,
            medium_severity_findings=analysis.medium_severity_findings,
            low_severity_findings=analysis.low_severity_findings,
            open_findings=_count_open_findings(analysis),
            provider=analysis.provider,
            model_name=analysis.model_name,
            patient=PatientSummaryResponse(
                id=analysis.patient.id,
                first_name=analysis.patient.first_name,
                last_name=analysis.patient.last_name,
            ),
        )
        for analysis in analyses
    ]
