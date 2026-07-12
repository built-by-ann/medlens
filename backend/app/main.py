from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes.auth import router as auth_router
from app.api.routes.clinical_documents import router as clinical_documents_router
from app.api.routes.medications import router as medications_router
from app.api.routes.users import router as users_router
from app.db.session import SessionLocal

app = FastAPI(title="MedLens API")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(clinical_documents_router)
app.include_router(medications_router)


@app.get("/")
def root():
    return {"message": "Welcome to MedLens API"}


@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()

        return JSONResponse(
            content={
                "status": "ok",
                "database": "connected",
            },
            status_code=200,
        )

    except Exception as error:
        return JSONResponse(
            content={
                "status": "error",
                "database": "disconnected",
                "detail": str(error),
            },
            status_code=503,
        )