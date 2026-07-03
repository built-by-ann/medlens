from fastapi import FastAPI
from sqlalchemy import text

from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.db.session import SessionLocal

app = FastAPI(title="MedLens API")

app.include_router(auth_router)
app.include_router(users_router)


@app.get("/")
def root():
    return {"message": "Welcome to MedLens API"}


@app.get("/health")
def health_check():
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()

        return {
            "status": "ok",
            "database": "connected",
        }

    except Exception as error:
        return {
            "status": "error",
            "database": "disconnected",
            "detail": str(error),
        }