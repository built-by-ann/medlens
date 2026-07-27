from pydantic import BaseModel, ConfigDict, Field


class Medication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    dosage: str | None = None
    route: str | None = None
    frequency: str | None = None
    status: str | None = None
    notes: str | None = None


class ClinicalSummary(BaseModel):
    """The AI provider's own structured output, parsed and validated.

    extra="forbid" is deliberate: a response with fields outside this shape
    means the model did not follow the prompt's contract, which should be
    treated as an invalid response rather than silently accepted.
    """

    model_config = ConfigDict(extra="forbid")

    medications: list[Medication]
    possible_inconsistencies: list[str]
    summary: str


class ClinicalNoteSummaryRequest(BaseModel):
    clinical_document_ids: list[int] = Field(min_length=1)


class ClinicalNoteSummaryResponse(ClinicalSummary):
    analysis_id: int
    provider: str
    model: str
