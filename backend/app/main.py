from fastapi import FastAPI

app = FastAPI(title="MedLens API")


@app.get("/")
def root():
    return {"message": "Welcome to MedLens API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
