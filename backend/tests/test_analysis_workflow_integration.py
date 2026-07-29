"""End-to-end integration test for the complete analysis workflow.

Unlike the per-component tests in test_analyses.py and test_analysis.py,
which each exercise one endpoint or function in isolation, this test chains
the whole workflow together in a single run (register, authenticate, upload
documents, summarize, retrieve, and confirm ownership enforcement) and
cross-checks that the two endpoints agree about the same persisted Analysis.
Only the AI provider is mocked; everything else runs through the real
FastAPI app, dependency injection, SQLAlchemy session, and database.
"""

import json

from app.ai.providers.base import AIProvider
from app.ai.service import AISummaryService, get_ai_summary_service
from app.main import app

RESPONSE_TEXT = json.dumps(
    {
        "medications": [
            {
                "name": "Lisinopril",
                "dosage": "10 mg",
                "route": "oral",
                "frequency": "once daily",
                "status": "active",
                "notes": None,
            },
            {
                "name": "Metformin",
                "dosage": "500 mg",
                "route": "oral",
                "frequency": "twice daily",
                "status": "active",
                "notes": None,
            },
        ],
        "possible_inconsistencies": [
            "Lisinopril dose differs between the visit note and the discharge summary.",
        ],
        "summary": "Patient is taking Lisinopril 10 mg and Metformin 500 mg.",
    }
)


def _register_and_login(client, email, password="correcthorse123"):
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "Workflow Test User"},
    )

    login_response = client.post("/auth/login", json={"email": email, "password": password})

    return login_response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_patient(client, token, **overrides):
    payload = {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": "1980-05-14",
    }
    payload.update(overrides)

    return client.post("/patients", json=payload, headers=_auth_headers(token))


def _create_document(client, token, patient_id, title, raw_text):
    response = client.post(
        f"/patients/{patient_id}/clinical-documents",
        json={"document_type": "visit_note", "title": title, "raw_text": raw_text},
        headers=_auth_headers(token),
    )

    return response.json()


class _FakeProvider(AIProvider):
    name = "fake-provider"
    model = "fake-model-v1"

    def __init__(self, text):
        self._text = text

    def generate_summary(self, prompt: str) -> str:
        return self._text


def _override_ai_service(fake_provider):
    def _factory():
        return AISummaryService(fake_provider)

    return _factory


def test_complete_analysis_workflow_from_summarize_through_retrieval(client):
    # 1-2. Create and authenticate a test user.
    token = _register_and_login(client, "workflow@example.com")
    assert token

    # 3. Prerequisite data: a patient, and two clinical documents scoped to
    # that patient, so the fake response's "possible_inconsistencies" entry
    # plausibly reflects disagreement between sources.
    patient = _create_patient(client, token).json()
    document_a = _create_document(
        client,
        token,
        patient["id"],
        "Visit Note",
        "Patient takes Lisinopril 10 mg oral once daily.",
    )
    document_b = _create_document(
        client,
        token,
        patient["id"],
        "Discharge Summary",
        "Continue Metformin 500 mg oral twice daily. Lisinopril dose unclear.",
    )

    # 4-6. Submit to /patients/{patient_id}/analyses with only the AI
    # provider mocked; request validation, authentication, the AIProvider
    # abstraction, Pydantic validation, and persistence all run for real.
    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(RESPONSE_TEXT)
    )
    try:
        summarize_response = client.post(
            f"/patients/{patient['id']}/analyses",
            json={"clinical_document_ids": [document_a["id"], document_b["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    # 7. Verify the API response.
    assert summarize_response.status_code == 201
    summarize_body = summarize_response.json()

    analysis_id = summarize_body["analysis_id"]
    assert isinstance(analysis_id, int)
    assert summarize_body["provider"] == "fake-provider"
    assert summarize_body["model"] == "fake-model-v1"
    assert summarize_body["summary"] == "Patient is taking Lisinopril 10 mg and Metformin 500 mg."
    assert {medication["name"] for medication in summarize_body["medications"]} == {
        "Lisinopril",
        "Metformin",
    }
    assert summarize_body["possible_inconsistencies"] == [
        "Lisinopril dose differs between the visit note and the discharge summary.",
    ]

    # 8. Retrieve the saved analysis through the read endpoint.
    detail_response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert detail_response.status_code == 200
    detail_body = detail_response.json()

    # 9. Verify the retrieved data matches what was created, covering every
    # assertion the issue requires: status, provider metadata, model_name,
    # timestamps, persisted mentions, and persisted inconsistencies.
    assert detail_body["id"] == analysis_id
    assert detail_body["patient_id"] == patient["id"]
    assert detail_body["status"] == "completed"
    assert detail_body["provider"] == "fake-provider"
    assert detail_body["model_name"] == "fake-model-v1"
    assert detail_body["error_message"] is None
    assert detail_body["started_at"] is not None
    assert detail_body["completed_at"] is not None
    assert detail_body["created_at"] is not None

    persisted_mentions = detail_body["medication_mentions"]
    assert {mention["medication_name"] for mention in persisted_mentions} == {
        "Lisinopril",
        "Metformin",
    }

    persisted_inconsistencies = detail_body["possible_inconsistencies"]
    assert len(persisted_inconsistencies) == 1
    assert (
        persisted_inconsistencies[0]["description"]
        == "Lisinopril dose differs between the visit note and the discharge summary."
    )

    # Cross-check: the two endpoints describe the same persisted analysis,
    # reached through two independent code paths.
    assert {medication["name"] for medication in summarize_body["medications"]} == {
        mention["medication_name"] for mention in persisted_mentions
    }

    # 11. Ownership enforcement still works: a second, unrelated user cannot
    # read this analysis, and gets the same 404 a nonexistent id would.
    other_user_token = _register_and_login(client, "workflow-intruder@example.com")

    forbidden_response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}",
        headers=_auth_headers(other_user_token),
    )

    assert forbidden_response.status_code == 404
