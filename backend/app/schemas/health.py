from typing import Literal

from pydantic import BaseModel


class DatabaseHealth(BaseModel):
    status: Literal["connected", "disconnected"]
    # Only present when status is "disconnected"; the same information
    # GET /health has always returned on a failed connectivity check, now
    # scoped to the database section it actually describes rather than a
    # top-level field (Issue #61).
    detail: str | None = None


class StorageHealth(BaseModel):
    # Settings.storage_backend verbatim ("local" or "s3"); never
    # constructs a StorageService to check this, so reporting it never
    # risks a real S3 call (see app/api/routes/health.py).
    backend: str


class AIHealth(BaseModel):
    # GeminiProvider.name, not a Settings field; there is no
    # provider-selection configuration today (only one AIProvider
    # implementation is ever wired up, see app/ai/service.py), so this
    # reports the actual class in use rather than inventing a redundant
    # setting that could drift out of sync with it.
    provider: str
    model: str


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    version: str
    environment: str
    database: DatabaseHealth
    storage: StorageHealth
    ai: AIHealth
    # UTC, formatted like "2026-08-04T02:15:30Z" (see
    # app/api/routes/health.py), a plain string, not a datetime field,
    # since the exact Z-suffixed format is part of this endpoint's
    # documented contract and a datetime field's default serialization
    # would produce a different (though equivalent) format.
    timestamp: str
