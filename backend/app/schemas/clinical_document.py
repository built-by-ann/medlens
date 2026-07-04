from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClinicalDocumentCreate(BaseModel):
    document_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    raw_text: str = Field(min_length=1)


class ClinicalDocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    document_type: str
    title: str
    raw_text: str
    file_name: str | None
    file_type: str | None
    created_at: datetime
    updated_at: datetime | None
