from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MedicationCreate(BaseModel):
    medication_name: str = Field(min_length=1)
    dose: str = Field(min_length=1)
    route: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    status: str = Field(min_length=1)
    source: str = Field(min_length=1)
    notes: str | None = None


class MedicationUpdate(BaseModel):
    medication_name: str | None = Field(default=None, min_length=1)
    dose: str | None = Field(default=None, min_length=1)
    route: str | None = Field(default=None, min_length=1)
    frequency: str | None = Field(default=None, min_length=1)
    status: str | None = Field(default=None, min_length=1)
    source: str | None = Field(default=None, min_length=1)
    notes: str | None = None


class MedicationImportSummary(BaseModel):
    rows_processed: int
    medications_created: int
    blank_rows_ignored: int


class MedicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    medication_name: str
    dose: str
    route: str
    frequency: str
    status: str
    source: str
    notes: str | None
    created_at: datetime
    updated_at: datetime | None
