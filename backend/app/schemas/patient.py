from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PatientCreate(BaseModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    date_of_birth: date
    external_mrn: str | None = None
    notes: str | None = None


class PatientUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1)
    last_name: str | None = Field(default=None, min_length=1)
    date_of_birth: date | None = None
    external_mrn: str | None = None
    notes: str | None = None


class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    first_name: str
    last_name: str
    date_of_birth: date
    external_mrn: str | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime | None


class PatientSummaryResponse(BaseModel):
    """Just enough to identify a patient inline in another resource's
    response (e.g. which patient a cross-patient analysis belongs to) -
    the same "nested citation, not the full resource" pattern as
    ClinicalDocumentSummaryResponse.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
