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

app = FastAPI(title="MedLens API")

# Vite's dev server picks the next free port (5173, 5174, ...) if the
# default is taken, so a fixed port list would break the next time that
# happens. A regex covers any localhost/127.0.0.1 port instead. This is
# intentionally restricted to non-production environments; a deployed
# frontend origin belongs in CORS_ALLOWED_ORIGINS instead, never here.
LOCALHOST_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1):\d+$"


def configure_cors(app: FastAPI, app_env: str, allowed_origins: list[str]) -> None:
    """Adds the CORS middleware. Extracted from module scope, with the
    environment and allowed origins passed in explicitly rather than read
    from the global settings object, purely so tests can exercise this
    against multiple environments without relying on process-wide state.
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=LOCALHOST_ORIGIN_REGEX if app_env == "development" else None,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


configure_cors(app, settings.app_env, settings.cors_allowed_origins_list)

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
