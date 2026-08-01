import json

import pytest

from app.ai.providers.base import AIProvider, AIProviderError
from app.ai.service import AISummaryService

VALID_RESPONSE = json.dumps(
    {
        "medications": [
            {
                "name": "Lisinopril",
                "dosage": "10 mg",
                "route": "oral",
                "frequency": "once daily",
                "status": "active",
                "notes": None,
            }
        ],
        "possible_inconsistencies": ["Dose differs between two notes."],
        "summary": "Patient is on Lisinopril 10 mg once daily.",
    }
)


class FakeProvider(AIProvider):
    name = "fake"
    model = "fake-model-1"

    def __init__(self, response_text=VALID_RESPONSE, error=None):
        self._response_text = response_text
        self._error = error
        self.last_prompt = None

    def generate_summary(self, prompt: str) -> str:
        self.last_prompt = prompt

        if self._error is not None:
            raise self._error

        return self._response_text


def test_summarize_returns_provider_and_model_metadata():
    provider = FakeProvider()
    service = AISummaryService(provider)

    result = service.summarize(["Some clinical note."])

    assert result.provider == "fake"
    assert result.model == "fake-model-1"


def test_summarize_returns_parsed_clinical_summary():
    provider = FakeProvider()
    service = AISummaryService(provider)

    result = service.summarize(["Some clinical note."])

    assert len(result.clinical_summary.medications) == 1
    medication = result.clinical_summary.medications[0]
    assert medication.name == "Lisinopril"
    assert medication.dosage == "10 mg"
    assert medication.route == "oral"
    assert medication.frequency == "once daily"
    assert medication.status == "active"
    assert medication.notes is None
    assert result.clinical_summary.possible_inconsistencies == ["Dose differs between two notes."]
    assert result.clinical_summary.summary == "Patient is on Lisinopril 10 mg once daily."


def test_summarize_allows_empty_medications_and_inconsistencies():
    response = json.dumps(
        {"medications": [], "possible_inconsistencies": [], "summary": "No medications noted."}
    )
    provider = FakeProvider(response_text=response)
    service = AISummaryService(provider)

    result = service.summarize(["Some clinical note."])

    assert result.clinical_summary.medications == []
    assert result.clinical_summary.possible_inconsistencies == []


def test_summarize_allows_optional_medication_fields_to_be_omitted():
    response = json.dumps(
        {
            "medications": [{"name": "Metformin"}],
            "possible_inconsistencies": [],
            "summary": "Patient takes Metformin.",
        }
    )
    provider = FakeProvider(response_text=response)
    service = AISummaryService(provider)

    result = service.summarize(["Some clinical note."])

    medication = result.clinical_summary.medications[0]
    assert medication.name == "Metformin"
    assert medication.dosage is None
    assert medication.route is None
    assert medication.frequency is None
    assert medication.status is None
    assert medication.notes is None
    assert medication.source_note is None


def test_summarize_parses_source_note_per_medication():
    # Issue #152: the same medication can legitimately appear more than
    # once, each tagged with a different source note, when it's mentioned
    # in more than one of the selected documents.
    response = json.dumps(
        {
            "medications": [
                {"name": "Lisinopril", "dosage": "10 mg", "source_note": 1},
                {"name": "Lisinopril", "dosage": "20 mg", "source_note": 2},
            ],
            "possible_inconsistencies": [],
            "summary": "Summary.",
        }
    )
    provider = FakeProvider(response_text=response)
    service = AISummaryService(provider)

    result = service.summarize(["Note one text.", "Note two text."])

    first, second = result.clinical_summary.medications
    assert first.source_note == 1
    assert second.source_note == 2


def test_summarize_builds_a_prompt_from_all_notes():
    provider = FakeProvider()
    service = AISummaryService(provider)

    service.summarize(["First note.", "Second note."])

    assert "First note." in provider.last_prompt
    assert "Second note." in provider.last_prompt


def test_summarize_propagates_provider_errors():
    provider = FakeProvider(error=AIProviderError("provider unavailable"))
    service = AISummaryService(provider)

    with pytest.raises(AIProviderError):
        service.summarize(["Some clinical note."])


def test_summarize_rejects_empty_notes_list():
    provider = FakeProvider()
    service = AISummaryService(provider)

    with pytest.raises(ValueError):
        service.summarize([])


def test_summarize_rejects_malformed_json():
    provider = FakeProvider(response_text="this is not json at all")
    service = AISummaryService(provider)

    with pytest.raises(AIProviderError):
        service.summarize(["Some clinical note."])


def test_summarize_rejects_missing_required_field():
    response = json.dumps({"medications": [], "possible_inconsistencies": []})
    provider = FakeProvider(response_text=response)
    service = AISummaryService(provider)

    with pytest.raises(AIProviderError):
        service.summarize(["Some clinical note."])


def test_summarize_rejects_missing_medication_name():
    response = json.dumps(
        {
            "medications": [{"dosage": "10 mg"}],
            "possible_inconsistencies": [],
            "summary": "Summary.",
        }
    )
    provider = FakeProvider(response_text=response)
    service = AISummaryService(provider)

    with pytest.raises(AIProviderError):
        service.summarize(["Some clinical note."])


def test_summarize_rejects_incorrect_field_type():
    response = json.dumps(
        {
            "medications": "Lisinopril 10 mg",
            "possible_inconsistencies": [],
            "summary": "Summary.",
        }
    )
    provider = FakeProvider(response_text=response)
    service = AISummaryService(provider)

    with pytest.raises(AIProviderError):
        service.summarize(["Some clinical note."])


def test_summarize_rejects_incorrect_medication_field_type():
    response = json.dumps(
        {
            "medications": [{"name": "Lisinopril", "dosage": 10}],
            "possible_inconsistencies": [],
            "summary": "Summary.",
        }
    )
    provider = FakeProvider(response_text=response)
    service = AISummaryService(provider)

    with pytest.raises(AIProviderError):
        service.summarize(["Some clinical note."])


def test_summarize_rejects_unexpected_top_level_field():
    response = json.dumps(
        {
            "medications": [],
            "possible_inconsistencies": [],
            "summary": "Summary.",
            "confidence": 0.9,
        }
    )
    provider = FakeProvider(response_text=response)
    service = AISummaryService(provider)

    with pytest.raises(AIProviderError):
        service.summarize(["Some clinical note."])


def test_summarize_rejects_unexpected_medication_field():
    response = json.dumps(
        {
            "medications": [{"name": "Lisinopril", "brand_name": "Prinivil"}],
            "possible_inconsistencies": [],
            "summary": "Summary.",
        }
    )
    provider = FakeProvider(response_text=response)
    service = AISummaryService(provider)

    with pytest.raises(AIProviderError):
        service.summarize(["Some clinical note."])


def test_summarize_rejects_unexpected_top_level_structure():
    response = json.dumps(["Lisinopril", "Metformin"])
    provider = FakeProvider(response_text=response)
    service = AISummaryService(provider)

    with pytest.raises(AIProviderError):
        service.summarize(["Some clinical note."])
