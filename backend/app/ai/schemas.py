from pydantic import BaseModel, ConfigDict, Field


class Medication(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    dosage: str | None = None
    route: str | None = None
    frequency: str | None = None
    status: str | None = None
    notes: str | None = None
    # 1-indexed position of the "Note N" (see app/ai/prompts.py's numbering)
    # this medication was actually found in, for true per-document
    # provenance (Issue #152); replaces the earlier placeholder that
    # attached every extracted medication to the same document regardless
    # of where it was mentioned. Optional, not required: a response that
    # omits it is still accepted (older prompt behavior, or a provider that
    # doesn't follow this part of the instructions) rather than rejecting
    # the whole analysis over one missing attribution; the persistence
    # layer falls back to a documented default when it's absent or out of
    # range (see reconcile_ai_extracted_medications).
    source_note: int | None = None


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
