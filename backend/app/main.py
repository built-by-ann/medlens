import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analyses import recent_analyses_router
from app.api.routes.analyses import router as analyses_router
from app.api.routes.auth import router as auth_router
from app.api.routes.clinical_documents import router as clinical_documents_router
from app.api.routes.health import router as health_router
from app.api.routes.medications import router as medications_router
from app.api.routes.patients import router as patients_router
from app.api.routes.users import router as users_router
from app.core.config import settings
from app.core.logging_config import (
    configure_exception_handling,
    configure_logging,
    configure_request_logging,
)

# Configured before anything else below runs (including FastAPI(...) itself)
# so even the earliest startup issue is logged consistently; see
# app/core/logging_config.py.
configure_logging(settings.app_env, settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    logger.info(
        "Application starting",
        extra={
            "event": "application_startup",
            "version": settings.app_version,
            "environment": settings.app_env,
            "storage_backend": settings.storage_backend,
        },
    )
    yield
    logger.info("Application shutting down", extra={"event": "application_shutdown"})


app = FastAPI(title="MedLens API", lifespan=lifespan)

# Vite's dev server picks the next free port (5173, 5174, ...) if the
# default is taken, so a fixed port list would break the next time that
# happens. A regex covers any localhost/127.0.0.1 port instead. This is
# intentionally restricted to non-production environments.
LOCALHOST_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1):\d+$"


def configure_cors(app: FastAPI, app_env: str) -> None:
    """Adds the CORS middleware. Extracted from module scope, with the
    environment passed in explicitly rather than read from the global
    settings object, purely so tests can exercise this against multiple
    environments without relying on process-wide state.

    Retained for exactly one case (Issue #190): `npm run dev`'s Vite dev
    server runs outside Docker and talks to this backend directly and
    cross-origin (see docs/deployment.md's Local Development section);
    that's the only real cross-origin request this application ever
    receives. Every other path, the Docker Compose / production frontend
    image, and any real deployment, now reaches this backend exclusively
    through the frontend container's own nginx reverse proxy
    (frontend/nginx.conf), which is same-origin from the browser's point
    of view and never triggers CORS at all. There is deliberately no
    allow_origins list for a deployed frontend origin anymore (Issue #57
    originally added CORS_ALLOWED_ORIGINS for exactly that, since removed;
    see docs/design-decisions.md, Decision 23); nothing outside local dev
    needs one, so allow_origins is always empty; only the regex below,
    itself already restricted to non-production, ever allows anything.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=LOCALHOST_ORIGIN_REGEX if app_env == "development" else None,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


configure_cors(app, settings.app_env)
# Request-scoped logging context (request_id/method/path/client_ip) and the
# one-line-per-request summary log, registered after CORS so a preflight
# OPTIONS request is still handled (and logged) the same as any other
# request; middleware order here doesn't otherwise interact with CORS at
# all. See app/core/logging_config.py.
configure_request_logging(app)
# Unhandled-exception logging (full traceback, server-side only) + a
# generic 500 response; see app/core/logging_config.py for why this never
# affects any existing `raise HTTPException(...)` throughout the app.
configure_exception_handling(app)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(clinical_documents_router)
app.include_router(medications_router)
app.include_router(patients_router)
app.include_router(analyses_router)
app.include_router(recent_analyses_router)


@app.get("/")
def root():
    return {"message": "Welcome to MedLens API"}
