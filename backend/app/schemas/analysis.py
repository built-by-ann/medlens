from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisCreate(BaseModel):
    clinical_document_ids: list[int] = Field(min_length=1)


class AnalysisCompletedSummary(BaseModel):
    summary: str | None = None
    total_findings: int = Field(ge=0)
    high_severity_findings: int = Field(ge=0)
    medium_severity_findings: int = Field(ge=0)
    low_severity_findings: int = Field(ge=0)
    provider: str | None = None
    model_name: str | None = None


class AnalysisFailure(BaseModel):
    error_message: str = Field(min_length=1)


class AnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: AnalysisStatus

    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None

    summary: str | None

    total_findings: int
    high_severity_findings: int
    medium_severity_findings: int
    low_severity_findings: int

    provider: str | None
    model_name: str | None

    created_at: datetime
    updated_at: datetime | None
