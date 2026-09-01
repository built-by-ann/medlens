from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.openbiollm_provider import OpenBioLLMProvider
from app.core.config import settings
from app.db.session import SessionLocal
from app.schemas.health import AIHealth, DatabaseHealth, HealthResponse, StorageHealth

router = APIRouter(tags=["health"])


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/health", response_model=HealthResponse)
def health_check() -> JSONResponse:
    """Lightweight, suitable for an automated health check (Issue #61):
    the only I/O is the one `SELECT 1` below, to a database this process
    already holds a connection pool for. Storage backend and AI
    provider/model are reported from settings already loaded into memory
    and a plain class attribute - never by constructing a StorageService
    (which would mean a real S3 call for the "s3" backend) or an AI
    provider client (which would mean contacting Gemini or Hugging Face),
    both explicitly ruled out by this endpoint's own requirements.

    Mirrors settings.ai_provider (validated at startup - see Settings'
    own model_validator) rather than hardcoding GeminiProvider: reporting
    "gemini" here while AI_PROVIDER=openbiollm is actually configured
    would make this endpoint actively misleading, not just incomplete.
    """
    version = settings.app_version
    environment = settings.app_env
    storage = StorageHealth(backend=settings.storage_backend)

    if settings.ai_provider == "openbiollm":
        ai = AIHealth(provider=OpenBioLLMProvider.name, model=settings.openbiollm_model)
    else:
        ai = AIHealth(provider=GeminiProvider.name, model=settings.gemini_model)

    timestamp = _utc_timestamp()

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()

        response = HealthResponse(
            status="ok",
            version=version,
            environment=environment,
            database=DatabaseHealth(status="connected"),
            storage=storage,
            ai=ai,
            timestamp=timestamp,
        )
        status_code = 200
    except Exception as error:
        response = HealthResponse(
            status="error",
            version=version,
            environment=environment,
            database=DatabaseHealth(status="disconnected", detail=str(error)),
            storage=storage,
            ai=ai,
            timestamp=timestamp,
        )
        status_code = 503

    return JSONResponse(content=response.model_dump(exclude_none=True), status_code=status_code)
