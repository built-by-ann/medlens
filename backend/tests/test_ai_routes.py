import json

from app.ai.providers.base import AIProvider, AIProviderError
from app.ai.service import AISummaryService, get_ai_summary_service
from app.main import app
from app.models.analysis import Analysis
from app.models.analysis_inconsistency import AnalysisInconsistency
from app.models.analysis_medication_mention import AnalysisMedicationMention

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
        "summary": "Lisinopril 10 mg noted.",
    }
)

NO_MEDICATIONS_RESPONSE = json.dumps(
    {
        "medications": [],
        "possible_inconsistencies": ["Some inconsistency."],
        "summary": "No medications found.",
    }
)

NO_INCONSISTENCIES_RESPONSE = json.dumps(
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
        "possible_inconsistencies": [],
        "summary": "No inconsistencies found.",
    }
)

MULTIPLE_ITEMS_RESPONSE = json.dumps(
    {
        "medications": [
            {"name": "Atorvastatin", "dosage": "20 mg"},
            {"name": "Lisinopril", "dosage": "10 mg"},
            {"name": "Metformin", "dosage": "500 mg"},
        ],
        "possible_inconsistencies": [
            "First inconsistency.",
            "Second inconsistency.",
            "Third inconsistency.",
        ],
        "summary": "Multiple items.",
    }
)


def _register_and_login(client, email, password="correcthorse123"):
    client.post(
        "/auth/register",
        json={"email": email, "password": password, "name": "AI Test User"},
    )

    login_response = client.post("/auth/login", json={"email": email, "password": password})

    return login_response.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_document(client, token, title="Visit Note", raw_text="Patient takes Lisinopril 10 mg."):
    response = client.post(
        "/clinical-documents",
        json={"document_type": "visit_note", "title": title, "raw_text": raw_text},
        headers=_auth_headers(token),
    )

    return response.json()


class _FakeProvider(AIProvider):
    name = "fake"
    model = "fake-model"

    def __init__(self, text=VALID_RESPONSE, error=None):
        self._text = text
        self._error = error

    def generate_summary(self, prompt: str) -> str:
        if self._error is not None:
            raise self._error

        return self._text


def _override_ai_service(fake_provider):
    def _factory():
        return AISummaryService(fake_provider)

    return _factory


def _create_completed_analysis(client, token, document_id, response_text=VALID_RESPONSE):
    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(text=response_text)
    )
    try:
        response = client.post(
            "/ai/summarize",
            json={"clinical_document_ids": [document_id]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 201
    return response.json()["analysis_id"]


def test_summarize_requires_authentication(client):
    response = client.post("/ai/summarize", json={"clinical_document_ids": [1]})

    assert response.status_code == 401


def test_summarize_persists_analysis_and_returns_summary_for_owned_documents(client, db):
    token = _register_and_login(client, "aisummary@example.com")
    document = _create_document(client, token)

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(_FakeProvider())
    try:
        response = client.post(
            "/ai/summarize",
            json={"clinical_document_ids": [document["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 201

    body = response.json()
    assert isinstance(body["analysis_id"], int)
    assert body["provider"] == "fake"
    assert body["model"] == "fake-model"
    assert body["summary"] == "Lisinopril 10 mg noted."
    assert body["possible_inconsistencies"] == ["Dose differs between two notes."]
    assert len(body["medications"]) == 1
    medication = body["medications"][0]
    assert medication["name"] == "Lisinopril"
    assert medication["dosage"] == "10 mg"
    assert medication["route"] == "oral"
    assert medication["frequency"] == "once daily"
    assert medication["status"] == "active"
    assert medication["notes"] is None

    analysis = db.get(Analysis, body["analysis_id"])
    assert analysis.status == "completed"
    assert analysis.completed_at is not None
    assert analysis.provider == "fake"
    assert analysis.model_name == "fake-model"
    assert analysis.summary == "Lisinopril 10 mg noted."

    mentions = (
        db.query(AnalysisMedicationMention)
        .filter(AnalysisMedicationMention.analysis_id == analysis.id)
        .all()
    )
    assert len(mentions) == 1
    assert mentions[0].medication_name == "Lisinopril"
    assert mentions[0].dosage == "10 mg"

    inconsistencies = (
        db.query(AnalysisInconsistency)
        .filter(AnalysisInconsistency.analysis_id == analysis.id)
        .all()
    )
    assert len(inconsistencies) == 1
    assert inconsistencies[0].description == "Dose differs between two notes."


def test_summarize_combines_multiple_documents(client):
    token = _register_and_login(client, "aisummarymulti@example.com")
    document_a = _create_document(client, token, title="Visit Note", raw_text="Note A text.")
    document_b = _create_document(client, token, title="Discharge Summary", raw_text="Note B text.")

    captured_prompts = []

    class _CapturingProvider(AIProvider):
        name = "fake"
        model = "fake-model"

        def generate_summary(self, prompt: str) -> str:
            captured_prompts.append(prompt)
            return VALID_RESPONSE

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _CapturingProvider()
    )
    try:
        response = client.post(
            "/ai/summarize",
            json={"clinical_document_ids": [document_a["id"], document_b["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 201
    assert "Note A text." in captured_prompts[0]
    assert "Note B text." in captured_prompts[0]


def test_summarize_rejects_nonexistent_document(client, db):
    token = _register_and_login(client, "aisummarymissing@example.com")

    response = client.post(
        "/ai/summarize",
        json={"clinical_document_ids": [999999]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404
    assert db.query(Analysis).count() == 0


def test_summarize_rejects_document_owned_by_another_user(client, db):
    token_a = _register_and_login(client, "aisummaryowner@example.com")
    token_b = _register_and_login(client, "aisummaryintruder@example.com")
    document = _create_document(client, token_a)

    response = client.post(
        "/ai/summarize",
        json={"clinical_document_ids": [document["id"]]},
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 404
    assert db.query(Analysis).count() == 0


def test_summarize_returns_503_when_provider_fails(client, db):
    token = _register_and_login(client, "aisummaryfailure@example.com")
    document = _create_document(client, token)

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(error=AIProviderError("Gemini API key is not configured"))
    )
    try:
        response = client.post(
            "/ai/summarize",
            json={"clinical_document_ids": [document["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 503
    assert response.json()["detail"] == "Gemini API key is not configured"

    analysis = db.query(Analysis).one()
    assert analysis.status == "failed"
    assert analysis.error_message == "Gemini API key is not configured"
    assert (
        db.query(AnalysisMedicationMention)
        .filter(AnalysisMedicationMention.analysis_id == analysis.id)
        .count()
        == 0
    )
    assert (
        db.query(AnalysisInconsistency)
        .filter(AnalysisInconsistency.analysis_id == analysis.id)
        .count()
        == 0
    )


def test_summarize_returns_503_when_provider_response_fails_validation(client, db):
    token = _register_and_login(client, "aisummaryinvalidjson@example.com")
    document = _create_document(client, token)

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(text="this is not json at all")
    )
    try:
        response = client.post(
            "/ai/summarize",
            json={"clinical_document_ids": [document["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 503

    analysis = db.query(Analysis).one()
    assert analysis.status == "failed"
    assert analysis.error_message == "AI response failed validation"


def test_summarize_rejects_empty_document_id_list(client):
    token = _register_and_login(client, "aisummaryemptylist@example.com")

    response = client.post(
        "/ai/summarize",
        json={"clinical_document_ids": []},
        headers=_auth_headers(token),
    )

    assert response.status_code == 422


def test_summarize_uses_real_gemini_provider_by_default_when_key_missing(client, db):
    # No dependency override here: exercises the real get_ai_summary_service
    # wiring end to end. With no GEMINI_API_KEY configured in the test
    # environment, this should fail gracefully as a 503, not a 500 or crash,
    # and the failure should still be persisted as a failed Analysis.
    token = _register_and_login(client, "aisummaryrealprovider@example.com")
    document = _create_document(client, token)

    response = client.post(
        "/ai/summarize",
        json={"clinical_document_ids": [document["id"]]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 503

    analysis = db.query(Analysis).one()
    assert analysis.status == "failed"
    assert analysis.error_message == "Gemini API key is not configured"


def test_get_analysis_detail_requires_authentication(client):
    response = client.get("/ai/analyses/1")

    assert response.status_code == 401


def test_get_analysis_detail_returns_persisted_analysis(client):
    token = _register_and_login(client, "analysisdetail@example.com")
    document = _create_document(client, token)
    analysis_id = _create_completed_analysis(client, token, document["id"])

    response = client.get(f"/ai/analyses/{analysis_id}", headers=_auth_headers(token))

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == analysis_id
    assert body["status"] == "completed"
    assert body["provider"] == "fake"
    assert body["model_name"] == "fake-model"
    assert body["summary"] == "Lisinopril 10 mg noted."
    assert body["started_at"] is not None
    assert body["completed_at"] is not None
    assert body["error_message"] is None
    assert body["created_at"] is not None
    assert "updated_at" in body

    assert len(body["medication_mentions"]) == 1
    mention = body["medication_mentions"][0]
    assert mention["medication_name"] == "Lisinopril"
    assert mention["dosage"] == "10 mg"
    assert mention["route"] == "oral"
    assert mention["frequency"] == "once daily"
    assert mention["status"] == "active"
    assert mention["notes"] is None

    assert len(body["possible_inconsistencies"]) == 1
    assert body["possible_inconsistencies"][0]["description"] == "Dose differs between two notes."


def test_get_analysis_detail_with_no_medications(client):
    token = _register_and_login(client, "detailnomedications@example.com")
    document = _create_document(client, token)
    analysis_id = _create_completed_analysis(
        client, token, document["id"], response_text=NO_MEDICATIONS_RESPONSE
    )

    response = client.get(f"/ai/analyses/{analysis_id}", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["medication_mentions"] == []
    assert len(response.json()["possible_inconsistencies"]) == 1


def test_get_analysis_detail_with_no_inconsistencies(client):
    token = _register_and_login(client, "detailnoinconsistencies@example.com")
    document = _create_document(client, token)
    analysis_id = _create_completed_analysis(
        client, token, document["id"], response_text=NO_INCONSISTENCIES_RESPONSE
    )

    response = client.get(f"/ai/analyses/{analysis_id}", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json()["possible_inconsistencies"] == []
    assert len(response.json()["medication_mentions"]) == 1


def test_get_analysis_detail_returns_items_in_deterministic_order(client):
    token = _register_and_login(client, "detailordering@example.com")
    document = _create_document(client, token)
    analysis_id = _create_completed_analysis(
        client, token, document["id"], response_text=MULTIPLE_ITEMS_RESPONSE
    )

    response = client.get(f"/ai/analyses/{analysis_id}", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()

    medication_names = [mention["medication_name"] for mention in body["medication_mentions"]]
    assert medication_names == ["Atorvastatin", "Lisinopril", "Metformin"]

    mention_ids = [mention["id"] for mention in body["medication_mentions"]]
    assert mention_ids == sorted(mention_ids)

    inconsistency_descriptions = [
        inconsistency["description"] for inconsistency in body["possible_inconsistencies"]
    ]
    assert inconsistency_descriptions == [
        "First inconsistency.",
        "Second inconsistency.",
        "Third inconsistency.",
    ]

    inconsistency_ids = [
        inconsistency["id"] for inconsistency in body["possible_inconsistencies"]
    ]
    assert inconsistency_ids == sorted(inconsistency_ids)


def test_get_analysis_detail_includes_sanitized_error_message_for_failed_analysis(client, db):
    token = _register_and_login(client, "detailfailedmessage@example.com")
    document = _create_document(client, token)

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(error=AIProviderError("Gemini API key is not configured"))
    )
    try:
        summarize_response = client.post(
            "/ai/summarize",
            json={"clinical_document_ids": [document["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert summarize_response.status_code == 503
    analysis_id = db.query(Analysis).one().id

    response = client.get(f"/ai/analyses/{analysis_id}", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "Gemini API key is not configured"
    assert body["summary"] is None
    assert body["provider"] is None
    assert body["model_name"] is None
    assert body["medication_mentions"] == []
    assert body["possible_inconsistencies"] == []


def test_get_analysis_detail_rejects_wrong_user(client):
    token_a = _register_and_login(client, "detailowner@example.com")
    token_b = _register_and_login(client, "detailintruder@example.com")
    document = _create_document(client, token_a)
    analysis_id = _create_completed_analysis(client, token_a, document["id"])

    response = client.get(f"/ai/analyses/{analysis_id}", headers=_auth_headers(token_b))

    assert response.status_code == 404


def test_get_analysis_detail_rejects_nonexistent_analysis(client):
    token = _register_and_login(client, "detailmissing@example.com")

    response = client.get("/ai/analyses/999999", headers=_auth_headers(token))

    assert response.status_code == 404


def test_delete_analysis_requires_authentication(client):
    response = client.delete("/ai/analyses/1")

    assert response.status_code == 401


def test_delete_analysis_removes_owned_analysis_and_its_children(client, db):
    token = _register_and_login(client, "deleteanalysis@example.com")
    document = _create_document(client, token)
    analysis_id = _create_completed_analysis(client, token, document["id"])

    response = client.delete(f"/ai/analyses/{analysis_id}", headers=_auth_headers(token))

    assert response.status_code == 204
    assert response.content == b""

    assert db.query(Analysis).filter(Analysis.id == analysis_id).first() is None
    assert (
        db.query(AnalysisMedicationMention)
        .filter(AnalysisMedicationMention.analysis_id == analysis_id)
        .count()
        == 0
    )
    assert (
        db.query(AnalysisInconsistency)
        .filter(AnalysisInconsistency.analysis_id == analysis_id)
        .count()
        == 0
    )

    # No longer retrievable through the read endpoint.
    get_response = client.get(f"/ai/analyses/{analysis_id}", headers=_auth_headers(token))
    assert get_response.status_code == 404


def test_delete_analysis_leaves_clinical_document_intact(client, db):
    token = _register_and_login(client, "deleteanalysiskeepdoc@example.com")
    document = _create_document(client, token)
    analysis_id = _create_completed_analysis(client, token, document["id"])

    response = client.delete(f"/ai/analyses/{analysis_id}", headers=_auth_headers(token))

    assert response.status_code == 204

    document_response = client.get(
        f"/clinical-documents/{document['id']}", headers=_auth_headers(token)
    )
    assert document_response.status_code == 200


def test_delete_analysis_rejects_wrong_user(client, db):
    token_a = _register_and_login(client, "deleteanalysisowner@example.com")
    token_b = _register_and_login(client, "deleteanalysisintruder@example.com")
    document = _create_document(client, token_a)
    analysis_id = _create_completed_analysis(client, token_a, document["id"])

    response = client.delete(f"/ai/analyses/{analysis_id}", headers=_auth_headers(token_b))

    assert response.status_code == 404
    assert db.query(Analysis).filter(Analysis.id == analysis_id).first() is not None


def test_delete_analysis_rejects_nonexistent_analysis(client):
    token = _register_and_login(client, "deleteanalysismissing@example.com")

    response = client.delete("/ai/analyses/999999", headers=_auth_headers(token))

    assert response.status_code == 404
