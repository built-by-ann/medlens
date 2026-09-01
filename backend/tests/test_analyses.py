import json
import logging

from app.ai.providers.base import AIProvider, AIProviderError
from app.ai.service import AISummaryService, get_ai_summary_service
from app.main import app
from app.models.analysis import Analysis
from app.models.analysis_inconsistency import AnalysisInconsistency
from app.models.analysis_medication_mention import AnalysisMedicationMention
from app.models.clinical_document import ClinicalDocument
from app.models.medication_discrepancy import MedicationDiscrepancy
from app.models.medication_mention import MedicationMention

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
        json={
            "email": email,
            "password": password,
            "username": email.split("@")[0].replace("-", "_")[:30],
            "name": "AI Test User",
        },
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


def _create_document(
    client,
    token,
    patient_id,
    title="Visit Note",
    raw_text="Patient takes Lisinopril 10 mg.",
    document_type="visit_note",
):
    response = client.post(
        f"/patients/{patient_id}/clinical-documents",
        json={"document_type": document_type, "title": title, "raw_text": raw_text},
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


def _create_medication(client, token, patient_id, **overrides):
    payload = {
        "medication_name": "Lisinopril",
        "dose": "10 mg",
        "route": "oral",
        "frequency": "once daily",
        "status": "active",
        "source": "patient_reported",
    }
    payload.update(overrides)

    return client.post(
        f"/patients/{patient_id}/medications", json=payload, headers=_auth_headers(token)
    )


def _create_completed_analysis(
    client, token, patient_id, document_id, response_text=VALID_RESPONSE
):
    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(text=response_text)
    )
    try:
        response = client.post(
            f"/patients/{patient_id}/analyses",
            json={"clinical_document_ids": [document_id]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 201
    return response.json()["analysis_id"]


# --- Timing (Issue #60) -------------------------------------------------


def test_summarize_logs_analysis_completed_duration_ms(client, caplog):
    token = _register_and_login(client, "analysistiming@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(_FakeProvider())
    caplog.set_level(logging.INFO)
    try:
        response = client.post(
            f"/patients/{patient['id']}/analyses",
            json={"clinical_document_ids": [document["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 201
    (record,) = [r for r in caplog.records if getattr(r, "event", None) == "analysis_completed"]
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0
    assert record.patient_id == patient["id"]
    assert record.analysis_id == response.json()["analysis_id"]


def test_summarize_logs_analysis_failed_duration_ms(client, caplog):
    token = _register_and_login(client, "analysistimingfail@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(error=AIProviderError("simulated provider failure"))
    )
    caplog.set_level(logging.INFO)
    try:
        response = client.post(
            f"/patients/{patient['id']}/analyses",
            json={"clinical_document_ids": [document["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 503
    (record,) = [r for r in caplog.records if getattr(r, "event", None) == "analysis_failed"]
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0
    assert record.patient_id == patient["id"]


def test_summarize_requires_authentication(client):
    response = client.post("/patients/1/analyses", json={"clinical_document_ids": [1]})

    assert response.status_code == 401


def test_old_flat_route_no_longer_exists(client):
    token = _register_and_login(client, "flatanalysisgone@example.com")

    response = client.post(
        "/ai/summarize",
        json={"clinical_document_ids": [1]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404


def test_summarize_requires_a_patient_owned_by_the_user(client):
    token_a = _register_and_login(client, "analysisowner4@example.com")
    token_b = _register_and_login(client, "analysisintruder4@example.com")
    patient = _create_patient(client, token_a).json()
    document = _create_document(client, token_a, patient["id"])

    response = client.post(
        f"/patients/{patient['id']}/analyses",
        json={"clinical_document_ids": [document["id"]]},
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Patient not found"


def test_summarize_persists_analysis_and_returns_summary_for_owned_documents(client, db):
    token = _register_and_login(client, "aisummary@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(_FakeProvider())
    try:
        response = client.post(
            f"/patients/{patient['id']}/analyses",
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
    assert analysis.patient_id == patient["id"]
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
    patient = _create_patient(client, token).json()
    document_a = _create_document(
        client, token, patient["id"], title="Visit Note", raw_text="Note A text."
    )
    document_b = _create_document(
        client, token, patient["id"], title="Discharge Summary", raw_text="Note B text."
    )

    captured_prompts = []

    class _CapturingProvider(AIProvider):
        name = "fake"
        model = "fake-model"

        def generate_summary(self, prompt: str) -> str:
            captured_prompts.append(prompt)
            return VALID_RESPONSE

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(_CapturingProvider())
    try:
        response = client.post(
            f"/patients/{patient['id']}/analyses",
            json={"clinical_document_ids": [document_a["id"], document_b["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 201
    assert "Note A text." in captured_prompts[0]
    assert "Note B text." in captured_prompts[0]


def test_summarize_reuses_previously_uploaded_documents_without_duplicating(client, db):
    # Issue #145: a provider can create an analysis from documents already
    # on a patient's record instead of re-uploading them. Mechanically this
    # endpoint has always accepted any clinical_document_ids the patient
    # owns regardless of when they were created (see
    # test_summarize_combines_multiple_documents), so no backend change was
    # needed; this test documents that reuse path explicitly and proves no
    # duplicate ClinicalDocument rows are created along the way.
    token = _register_and_login(client, "reuseexisting@example.com")
    patient = _create_patient(client, token).json()

    first_document = _create_document(client, token, patient["id"], title="Visit Note")
    second_document = _create_document(
        client,
        token,
        patient["id"],
        title="Discharge Summary",
        raw_text="Patient takes Metformin 500 mg.",
    )

    document_count_before = (
        db.query(ClinicalDocument).filter(ClinicalDocument.patient_id == patient["id"]).count()
    )
    assert document_count_before == 2

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(_FakeProvider())
    try:
        response = client.post(
            f"/patients/{patient['id']}/analyses",
            json={"clinical_document_ids": [first_document["id"], second_document["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 201
    analysis_id = response.json()["analysis_id"]

    document_count_after = (
        db.query(ClinicalDocument).filter(ClinicalDocument.patient_id == patient["id"]).count()
    )
    assert document_count_after == document_count_before

    list_response = client.get(f"/patients/{patient['id']}/analyses", headers=_auth_headers(token))
    analysis_row = next(row for row in list_response.json() if row["id"] == analysis_id)
    assert analysis_row["document_count"] == 2


def test_summarize_rejects_nonexistent_document(client, db):
    token = _register_and_login(client, "aisummarymissing@example.com")
    patient = _create_patient(client, token).json()

    response = client.post(
        f"/patients/{patient['id']}/analyses",
        json={"clinical_document_ids": [999999]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404
    assert db.query(Analysis).count() == 0


def test_summarize_rejects_document_owned_by_another_user(client, db):
    token_a = _register_and_login(client, "aisummaryowner@example.com")
    token_b = _register_and_login(client, "aisummaryintruder@example.com")
    patient_a = _create_patient(client, token_a).json()
    patient_b = _create_patient(client, token_b).json()
    document = _create_document(client, token_a, patient_a["id"])

    response = client.post(
        f"/patients/{patient_b['id']}/analyses",
        json={"clinical_document_ids": [document["id"]]},
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 404
    assert db.query(Analysis).count() == 0


def test_summarize_rejects_document_belonging_to_a_different_patient_of_the_same_user(client, db):
    token = _register_and_login(client, "aisummarycrosspatient@example.com")
    patient_a = _create_patient(client, token, first_name="A").json()
    patient_b = _create_patient(client, token, first_name="B").json()
    document = _create_document(client, token, patient_a["id"])

    response = client.post(
        f"/patients/{patient_b['id']}/analyses",
        json={"clinical_document_ids": [document["id"]]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404
    assert db.query(Analysis).count() == 0


def test_summarize_rejects_mixed_patient_document_sets(client, db):
    token = _register_and_login(client, "aisummarymixed@example.com")
    patient_a = _create_patient(client, token, first_name="A").json()
    patient_b = _create_patient(client, token, first_name="B").json()
    document_a = _create_document(client, token, patient_a["id"])
    document_b = _create_document(client, token, patient_b["id"])

    response = client.post(
        f"/patients/{patient_a['id']}/analyses",
        json={"clinical_document_ids": [document_a["id"], document_b["id"]]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 404
    assert db.query(Analysis).count() == 0


def test_summarize_returns_503_when_provider_fails(client, db):
    token = _register_and_login(client, "aisummaryfailure@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(error=AIProviderError("Gemini API key is not configured"))
    )
    try:
        response = client.post(
            f"/patients/{patient['id']}/analyses",
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
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(text="this is not json at all")
    )
    try:
        response = client.post(
            f"/patients/{patient['id']}/analyses",
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
    patient = _create_patient(client, token).json()

    response = client.post(
        f"/patients/{patient['id']}/analyses",
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
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    response = client.post(
        f"/patients/{patient['id']}/analyses",
        json={"clinical_document_ids": [document["id"]]},
        headers=_auth_headers(token),
    )

    assert response.status_code == 503

    analysis = db.query(Analysis).one()
    assert analysis.status == "failed"
    assert analysis.error_message == "Gemini API key is not configured"


def test_get_analysis_detail_requires_authentication(client):
    response = client.get("/patients/1/analyses/1")

    assert response.status_code == 401


def test_get_analysis_detail_returns_persisted_analysis(client):
    token = _register_and_login(client, "analysisdetail@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200

    body = response.json()
    assert body["id"] == analysis_id
    assert body["patient_id"] == patient["id"]
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
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(
        client, token, patient["id"], document["id"], response_text=NO_MEDICATIONS_RESPONSE
    )

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["medication_mentions"] == []
    assert len(response.json()["possible_inconsistencies"]) == 1


def test_get_analysis_detail_with_no_inconsistencies(client):
    token = _register_and_login(client, "detailnoinconsistencies@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(
        client, token, patient["id"], document["id"], response_text=NO_INCONSISTENCIES_RESPONSE
    )

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["possible_inconsistencies"] == []
    assert len(response.json()["medication_mentions"]) == 1


def test_get_analysis_detail_returns_items_in_deterministic_order(client):
    token = _register_and_login(client, "detailordering@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(
        client, token, patient["id"], document["id"], response_text=MULTIPLE_ITEMS_RESPONSE
    )

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

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

    inconsistency_ids = [inconsistency["id"] for inconsistency in body["possible_inconsistencies"]]
    assert inconsistency_ids == sorted(inconsistency_ids)


def test_get_analysis_detail_includes_document_count(client):
    # Issue #47: the Analysis Results page's AI Summary metadata shows how
    # many documents were analyzed.
    token = _register_and_login(client, "detaildoccount@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )
    assert response.status_code == 200
    assert response.json()["document_count"] == 1


def test_get_analysis_detail_document_count_reflects_every_selected_document(client):
    token = _register_and_login(client, "detaildoccountmulti@example.com")
    patient = _create_patient(client, token).json()
    document_a = _create_document(client, token, patient["id"], title="Visit Note A")
    document_b = _create_document(client, token, patient["id"], title="Visit Note B")

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(_FakeProvider())
    try:
        response = client.post(
            f"/patients/{patient['id']}/analyses",
            json={"clinical_document_ids": [document_a["id"], document_b["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 201
    analysis_id = response.json()["analysis_id"]

    detail_response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )
    assert detail_response.json()["document_count"] == 2


def test_get_analysis_detail_includes_reconciliation_discrepancies(client):
    # Issue #148: reconciliation now runs automatically during analysis
    # creation. This patient has no medications on file, so the
    # AI-extracted Lisinopril mention is necessarily missing from the list.
    token = _register_and_login(client, "detaildiscrepancies@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    body = response.json()

    assert len(body["medication_discrepancies"]) == 1
    discrepancy = body["medication_discrepancies"][0]
    assert discrepancy["analysis_id"] == analysis_id
    assert discrepancy["discrepancy_type"] == "missing_from_medication_list"
    assert discrepancy["severity"] == "high"
    assert discrepancy["resolution_status"] == "open"
    assert discrepancy["medication_mention_id"] is not None


def test_get_analysis_detail_nests_mention_evidence_with_source_document(client):
    # Issue #46: the discrepancy's supporting evidence, the MedicationMention
    # that triggered it, and that mention's own source document, is nested
    # directly in the response rather than requiring a second request.
    token = _register_and_login(client, "detailevidence@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"], title="March Visit Note")
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    discrepancy = response.json()["medication_discrepancies"][0]

    assert discrepancy["medication"] is None
    mention = discrepancy["medication_mention"]
    assert mention is not None
    assert mention["medication_name"] == "Lisinopril"
    assert mention["dose"] == "10 mg"
    assert mention["route"] == "oral"
    assert mention["frequency"] == "once daily"
    assert mention["status"] == "active"

    source_document = mention["clinical_document"]
    assert source_document["id"] == document["id"]
    assert source_document["title"] == "March Visit Note"
    assert source_document["document_type"] == "visit_note"
    # The evidence citation deliberately excludes the document's full text.
    assert "raw_text" not in source_document


def test_get_analysis_detail_attributes_each_medication_to_its_true_source_document(client):
    # Issue #152: two documents selected, two different medications each
    # reported against a different numbered note. Before this issue, both
    # mentions would have been attached to whichever selected document had
    # the lowest id, regardless of which note they actually came from; this
    # proves the nested evidence now cites each medication's true source.
    token = _register_and_login(client, "detailtrueprovenance@example.com")
    patient = _create_patient(client, token).json()
    document_a = _create_document(
        client, token, patient["id"], title="Visit Note", raw_text="Note A text."
    )
    document_b = _create_document(
        client, token, patient["id"], title="Discharge Summary", raw_text="Note B text."
    )

    response_text = json.dumps(
        {
            "medications": [
                {"name": "Lisinopril", "dosage": "10 mg", "source_note": 1},
                {"name": "Metformin", "dosage": "500 mg", "source_note": 2},
            ],
            "possible_inconsistencies": [],
            "summary": "Two medications noted.",
        }
    )

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(text=response_text)
    )
    try:
        create_response = client.post(
            f"/patients/{patient['id']}/analyses",
            json={"clinical_document_ids": [document_a["id"], document_b["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert create_response.status_code == 201
    analysis_id = create_response.json()["analysis_id"]

    detail_response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )
    assert detail_response.status_code == 200

    discrepancies = detail_response.json()["medication_discrepancies"]
    assert len(discrepancies) == 2

    source_document_by_medication = {
        discrepancy["medication_mention"]["medication_name"]: discrepancy["medication_mention"][
            "clinical_document"
        ]["id"]
        for discrepancy in discrepancies
    }
    assert source_document_by_medication == {
        "Lisinopril": document_a["id"],
        "Metformin": document_b["id"],
    }


def test_get_analysis_detail_nests_medication_evidence_for_unsupported_entry(client):
    # "unsupported_medication_list_entry" is only checked when a selected
    # document is medication-list-shaped (see UNSUPPORTED_ENTRY_ELIGIBLE_DOCUMENT_TYPES
    # in medication_reconciliation_service.py); this is the one finding
    # type whose evidence is the patient's own Medication row rather than a
    # MedicationMention, since it fires precisely because nothing mentions it.
    token = _register_and_login(client, "detailmedicationevidence@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(
        client,
        token,
        patient["id"],
        raw_text="Patient reports taking Metformin 500 mg.",
        document_type="medication_list",
    )
    medication_response = _create_medication(
        client, token, patient["id"], medication_name="Warfarin", dose="5 mg"
    )
    assert medication_response.status_code == 201

    metformin_response = json.dumps(
        {
            "medications": [{"name": "Metformin", "dosage": "500 mg"}],
            "possible_inconsistencies": [],
            "summary": "Metformin 500 mg noted.",
        }
    )
    analysis_id = _create_completed_analysis(
        client, token, patient["id"], document["id"], response_text=metformin_response
    )

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    discrepancies = response.json()["medication_discrepancies"]

    unsupported = next(
        d for d in discrepancies if d["discrepancy_type"] == "unsupported_medication_list_entry"
    )
    assert unsupported["medication_mention"] is None
    assert unsupported["medication"]["medication_name"] == "Warfarin"
    assert unsupported["medication"]["dose"] == "5 mg"

    missing = next(
        d for d in discrepancies if d["discrepancy_type"] == "missing_from_medication_list"
    )
    assert missing["medication"] is None
    assert missing["medication_mention"]["medication_name"] == "Metformin"


def test_get_analysis_detail_has_no_discrepancies_when_medications_match(client):
    token = _register_and_login(client, "detailmatching@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    medication_response = _create_medication(client, token, patient["id"])
    assert medication_response.status_code == 201

    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    assert response.json()["medication_discrepancies"] == []


def test_get_analysis_detail_does_not_duplicate_discrepancies_for_repeated_medications(client):
    # MULTIPLE_ITEMS_RESPONSE extracts three distinct medication names, none
    # of which are on this patient's (empty) medication list; three
    # findings, not more, even though building them involves grouping logic
    # that could in principle double-count.
    token = _register_and_login(client, "detaildedupe@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(
        client, token, patient["id"], document["id"], response_text=MULTIPLE_ITEMS_RESPONSE
    )

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    discrepancies = response.json()["medication_discrepancies"]
    assert len(discrepancies) == 3
    assert {d["discrepancy_type"] for d in discrepancies} == {"missing_from_medication_list"}


def test_summarize_leaves_no_discrepancies_or_mentions_when_reconciliation_fails(
    client, db, monkeypatch
):
    # Simulates the AI call succeeding but reconciliation itself failing
    # afterward; the whole analysis must still fail cleanly (existing
    # failure behavior), with nothing reconciliation staged left behind.
    token = _register_and_login(client, "reconciliationfailure@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated reconciliation failure")

    monkeypatch.setattr(
        "app.services.analysis_result_service.reconcile_ai_extracted_medications", _boom
    )

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(_FakeProvider())
    try:
        response = client.post(
            f"/patients/{patient['id']}/analyses",
            json={"clinical_document_ids": [document["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert response.status_code == 503
    assert "internal error" in response.json()["detail"]

    analysis = db.query(Analysis).one()
    assert analysis.status == "failed"
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
    assert db.query(MedicationMention).count() == 0
    assert (
        db.query(MedicationDiscrepancy)
        .filter(MedicationDiscrepancy.analysis_id == analysis.id)
        .count()
        == 0
    )


def test_get_analysis_detail_includes_sanitized_error_message_for_failed_analysis(client, db):
    token = _register_and_login(client, "detailfailedmessage@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    app.dependency_overrides[get_ai_summary_service] = _override_ai_service(
        _FakeProvider(error=AIProviderError("Gemini API key is not configured"))
    )
    try:
        summarize_response = client.post(
            f"/patients/{patient['id']}/analyses",
            json={"clinical_document_ids": [document["id"]]},
            headers=_auth_headers(token),
        )
    finally:
        app.dependency_overrides.pop(get_ai_summary_service, None)

    assert summarize_response.status_code == 503
    analysis_id = db.query(Analysis).one().id

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

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
    patient = _create_patient(client, token_a).json()
    document = _create_document(client, token_a, patient["id"])
    analysis_id = _create_completed_analysis(client, token_a, patient["id"], document["id"])

    response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token_b)
    )

    assert response.status_code == 404


def test_get_analysis_detail_rejects_a_different_patient_of_the_same_user(client):
    token = _register_and_login(client, "detailcrosspatient@example.com")
    patient_a = _create_patient(client, token, first_name="A").json()
    patient_b = _create_patient(client, token, first_name="B").json()
    document = _create_document(client, token, patient_a["id"])
    analysis_id = _create_completed_analysis(client, token, patient_a["id"], document["id"])

    response = client.get(
        f"/patients/{patient_b['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 404


def test_get_analysis_detail_rejects_nonexistent_analysis(client):
    token = _register_and_login(client, "detailmissing@example.com")
    patient = _create_patient(client, token).json()

    response = client.get(
        f"/patients/{patient['id']}/analyses/999999", headers=_auth_headers(token)
    )

    assert response.status_code == 404


def test_delete_analysis_requires_authentication(client):
    response = client.delete("/patients/1/analyses/1")

    assert response.status_code == 401


def test_delete_analysis_removes_owned_analysis_and_its_children(client, db):
    token = _register_and_login(client, "deleteanalysis@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.delete(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

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
    get_response = client.get(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )
    assert get_response.status_code == 404


def test_delete_analysis_leaves_clinical_document_intact(client, db):
    token = _register_and_login(client, "deleteanalysiskeepdoc@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.delete(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 204

    document_response = client.get(
        f"/patients/{patient['id']}/clinical-documents/{document['id']}",
        headers=_auth_headers(token),
    )
    assert document_response.status_code == 200


def test_delete_analysis_rejects_wrong_user(client, db):
    token_a = _register_and_login(client, "deleteanalysisowner@example.com")
    token_b = _register_and_login(client, "deleteanalysisintruder@example.com")
    patient = _create_patient(client, token_a).json()
    document = _create_document(client, token_a, patient["id"])
    analysis_id = _create_completed_analysis(client, token_a, patient["id"], document["id"])

    response = client.delete(
        f"/patients/{patient['id']}/analyses/{analysis_id}", headers=_auth_headers(token_b)
    )

    assert response.status_code == 404
    assert db.query(Analysis).filter(Analysis.id == analysis_id).first() is not None


def test_delete_analysis_rejects_a_different_patient_of_the_same_user(client, db):
    token = _register_and_login(client, "deleteanalysiscrosspatient@example.com")
    patient_a = _create_patient(client, token, first_name="A").json()
    patient_b = _create_patient(client, token, first_name="B").json()
    document = _create_document(client, token, patient_a["id"])
    analysis_id = _create_completed_analysis(client, token, patient_a["id"], document["id"])

    response = client.delete(
        f"/patients/{patient_b['id']}/analyses/{analysis_id}", headers=_auth_headers(token)
    )

    assert response.status_code == 404
    assert db.query(Analysis).filter(Analysis.id == analysis_id).first() is not None


def test_delete_analysis_rejects_nonexistent_analysis(client):
    token = _register_and_login(client, "deleteanalysismissing@example.com")
    patient = _create_patient(client, token).json()

    response = client.delete(
        f"/patients/{patient['id']}/analyses/999999", headers=_auth_headers(token)
    )

    assert response.status_code == 404


def test_list_analyses_requires_authentication(client):
    response = client.get("/patients/1/analyses")

    assert response.status_code == 401


def test_list_analyses_returns_empty_list_for_new_patient(client):
    token = _register_and_login(client, "listanalysesempty@example.com")
    patient = _create_patient(client, token).json()

    response = client.get(f"/patients/{patient['id']}/analyses", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json() == []


def test_list_analyses_returns_expected_fields(client):
    token = _register_and_login(client, "listanalysesfields@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.get(f"/patients/{patient['id']}/analyses", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["id"] == analysis_id
    assert item["patient_id"] == patient["id"]
    assert item["status"] == "completed"
    assert item["document_count"] == 1
    assert item["summary"] == "Lisinopril 10 mg noted."
    assert item["provider"] == "fake"
    assert item["model_name"] == "fake-model"
    assert item["error_message"] is None
    assert item["created_at"] is not None
    assert item["completed_at"] is not None
    assert "total_findings" in item
    assert "high_severity_findings" in item
    assert "medium_severity_findings" in item
    assert "low_severity_findings" in item
    # List rows never include full mention/inconsistency detail.
    assert "medication_mentions" not in item
    assert "possible_inconsistencies" not in item


def test_list_analyses_only_returns_the_given_patients_analyses(client):
    token_a = _register_and_login(client, "listanalysesowner@example.com")
    token_b = _register_and_login(client, "listanalysesintruder@example.com")
    patient_a = _create_patient(client, token_a).json()
    patient_b = _create_patient(client, token_b).json()
    document_a = _create_document(client, token_a, patient_a["id"])
    document_b = _create_document(client, token_b, patient_b["id"])

    owned_analysis_id = _create_completed_analysis(
        client, token_a, patient_a["id"], document_a["id"]
    )
    _create_completed_analysis(client, token_b, patient_b["id"], document_b["id"])

    response = client.get(f"/patients/{patient_a['id']}/analyses", headers=_auth_headers(token_a))

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [owned_analysis_id]


def test_list_analyses_excludes_a_different_patient_of_the_same_user(client):
    token = _register_and_login(client, "listanalysescrosspatient@example.com")
    patient_a = _create_patient(client, token, first_name="A").json()
    patient_b = _create_patient(client, token, first_name="B").json()
    document_a = _create_document(client, token, patient_a["id"])

    analysis_a_id = _create_completed_analysis(client, token, patient_a["id"], document_a["id"])

    response_a = client.get(f"/patients/{patient_a['id']}/analyses", headers=_auth_headers(token))
    response_b = client.get(f"/patients/{patient_b['id']}/analyses", headers=_auth_headers(token))

    assert [item["id"] for item in response_a.json()] == [analysis_a_id]
    assert response_b.json() == []


def test_list_analyses_rejects_a_patient_owned_by_another_user(client):
    token_a = _register_and_login(client, "listanalysesownerreject@example.com")
    token_b = _register_and_login(client, "listanalysesintruderreject@example.com")
    patient = _create_patient(client, token_a).json()

    response = client.get(f"/patients/{patient['id']}/analyses", headers=_auth_headers(token_b))

    assert response.status_code == 404


def test_list_analyses_orders_most_recent_first(client):
    token = _register_and_login(client, "listanalysesorder@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    first_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    second_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    third_id = _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.get(f"/patients/{patient['id']}/analyses", headers=_auth_headers(token))

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [third_id, second_id, first_id]


def test_list_analyses_respects_limit_query_param(client):
    token = _register_and_login(client, "listanalyseslimit@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    for _ in range(3):
        _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.get(
        f"/patients/{patient['id']}/analyses?limit=2", headers=_auth_headers(token)
    )

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_analyses_rejects_limit_out_of_range(client):
    token = _register_and_login(client, "listanalyseslimitinvalid@example.com")
    patient = _create_patient(client, token).json()

    response = client.get(
        f"/patients/{patient['id']}/analyses?limit=0", headers=_auth_headers(token)
    )
    assert response.status_code == 422

    response = client.get(
        f"/patients/{patient['id']}/analyses?limit=51", headers=_auth_headers(token)
    )
    assert response.status_code == 422


def test_recent_analyses_requires_authentication(client):
    response = client.get("/analyses/recent")

    assert response.status_code == 401


def test_recent_analyses_returns_empty_list_when_user_has_no_analyses(client):
    token = _register_and_login(client, "recentanalysesnone@example.com")

    response = client.get("/analyses/recent", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json() == []


def test_recent_analyses_spans_multiple_patients_and_identifies_each_one(client):
    token = _register_and_login(client, "recentanalysesspan@example.com")
    patient_a = _create_patient(client, token, first_name="Jane", last_name="Doe").json()
    patient_b = _create_patient(client, token, first_name="John", last_name="Smith").json()
    document_a = _create_document(client, token, patient_a["id"])
    document_b = _create_document(client, token, patient_b["id"])

    analysis_a_id = _create_completed_analysis(client, token, patient_a["id"], document_a["id"])
    analysis_b_id = _create_completed_analysis(client, token, patient_b["id"], document_b["id"])

    response = client.get("/analyses/recent", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [analysis_b_id, analysis_a_id]

    by_id = {item["id"]: item for item in body}
    assert by_id[analysis_a_id]["patient"] == {
        "id": patient_a["id"],
        "first_name": "Jane",
        "last_name": "Doe",
    }
    assert by_id[analysis_b_id]["patient"] == {
        "id": patient_b["id"],
        "first_name": "John",
        "last_name": "Smith",
    }


def test_recent_analyses_excludes_another_users_analyses(client):
    token_a = _register_and_login(client, "recentanalysesownera@example.com")
    token_b = _register_and_login(client, "recentanalysesownerb@example.com")
    patient_a = _create_patient(client, token_a).json()
    document_a = _create_document(client, token_a, patient_a["id"])
    _create_completed_analysis(client, token_a, patient_a["id"], document_a["id"])

    response = client.get("/analyses/recent", headers=_auth_headers(token_b))

    assert response.status_code == 200
    assert response.json() == []


def test_recent_analyses_excludes_analyses_belonging_to_archived_patients(client):
    token = _register_and_login(client, "recentanalysesarchived@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    _create_completed_analysis(client, token, patient["id"], document["id"])

    archive_response = client.delete(f"/patients/{patient['id']}", headers=_auth_headers(token))
    assert archive_response.status_code == 204

    response = client.get("/analyses/recent", headers=_auth_headers(token))

    assert response.status_code == 200
    assert response.json() == []


def test_recent_analyses_respects_limit_query_param(client):
    token = _register_and_login(client, "recentanalyseslimit@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])

    for _ in range(3):
        _create_completed_analysis(client, token, patient["id"], document["id"])

    response = client.get("/analyses/recent?limit=2", headers=_auth_headers(token))

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_recent_analyses_rejects_limit_out_of_range(client):
    token = _register_and_login(client, "recentanalyseslimitinvalid@example.com")

    response = client.get("/analyses/recent?limit=0", headers=_auth_headers(token))
    assert response.status_code == 422

    response = client.get("/analyses/recent?limit=51", headers=_auth_headers(token))
    assert response.status_code == 422


# --- POST /patients/{patient_id}/analyses/{analysis_id}/discrepancies/{discrepancy_id}/resolve ---


def _get_discrepancies(client, token, patient_id, analysis_id):
    response = client.get(
        f"/patients/{patient_id}/analyses/{analysis_id}", headers=_auth_headers(token)
    )
    assert response.status_code == 200
    return response.json()["medication_discrepancies"]


def _resolve(client, token, patient_id, analysis_id, discrepancy_id, payload):
    return client.post(
        f"/patients/{patient_id}/analyses/{analysis_id}/discrepancies/{discrepancy_id}/resolve",
        json=payload,
        headers=_auth_headers(token),
    )


def test_resolve_discrepancy_accepts_add_medication(client):
    # Patient has no medications on file, so the AI-extracted Lisinopril
    # mention is "missing from the medication list": the one discrepancy
    # type add_medication is valid for.
    token = _register_and_login(client, "resolveaddmedication@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    discrepancy = _get_discrepancies(client, token, patient["id"], analysis_id)[0]
    assert discrepancy["discrepancy_type"] == "missing_from_medication_list"

    response = _resolve(
        client,
        token,
        patient["id"],
        analysis_id,
        discrepancy["id"],
        {
            "action": "add_medication",
            "medication_name": "Lisinopril",
            "dose": "10 mg",
            "route": "oral",
            "frequency": "once daily",
            "status": "active",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resolution_status"] == "resolved"
    assert body["resolution_action"] == "add_medication"
    assert body["medication_id"] is not None

    medications = client.get(
        f"/patients/{patient['id']}/medications", headers=_auth_headers(token)
    ).json()
    assert len(medications) == 1
    assert medications[0]["id"] == body["medication_id"]
    assert medications[0]["medication_name"] == "Lisinopril"
    assert medications[0]["source"] == "reconciliation"


def test_resolve_discrepancy_accepts_update_medication_for_dose_conflict(client):
    token = _register_and_login(client, "resolveupdatedose@example.com")
    patient = _create_patient(client, token).json()
    # Existing medication says 20 mg; the AI-extracted mention (VALID_RESPONSE)
    # says 10 mg: a dose conflict, not "missing".
    _create_medication(client, token, patient["id"], dose="20 mg")
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    discrepancy = _get_discrepancies(client, token, patient["id"], analysis_id)[0]
    assert discrepancy["discrepancy_type"] == "dose_conflict"
    assert discrepancy["medication_id"] is not None

    response = _resolve(
        client,
        token,
        patient["id"],
        analysis_id,
        discrepancy["id"],
        {"action": "update_medication", "dose": "10 mg"},
    )

    assert response.status_code == 200
    assert response.json()["resolution_status"] == "resolved"
    assert response.json()["resolution_action"] == "update_medication"

    medications = client.get(
        f"/patients/{patient['id']}/medications", headers=_auth_headers(token)
    ).json()
    assert medications[0]["dose"] == "10 mg"


def test_resolve_discrepancy_accepts_mark_discontinued(client):
    token = _register_and_login(client, "resolvediscontinued@example.com")
    patient = _create_patient(client, token).json()
    _create_medication(client, token, patient["id"], status="active")
    document = _create_document(client, token, patient["id"])
    # VALID_RESPONSE's Lisinopril mention has status "active" too, so use a
    # response that reports it discontinued to trigger discontinued_status_conflict.
    response_text = json.dumps(
        {
            "medications": [
                {
                    "name": "Lisinopril",
                    "dosage": "10 mg",
                    "route": "oral",
                    "frequency": "once daily",
                    "status": "discontinued",
                    "notes": None,
                }
            ],
            "possible_inconsistencies": [],
            "summary": "Lisinopril discontinued.",
        }
    )
    analysis_id = _create_completed_analysis(
        client, token, patient["id"], document["id"], response_text=response_text
    )
    discrepancy = _get_discrepancies(client, token, patient["id"], analysis_id)[0]
    assert discrepancy["discrepancy_type"] == "discontinued_status_conflict"

    response = _resolve(
        client,
        token,
        patient["id"],
        analysis_id,
        discrepancy["id"],
        {"action": "update_medication", "status": "discontinued"},
    )

    assert response.status_code == 200
    medications = client.get(
        f"/patients/{patient['id']}/medications", headers=_auth_headers(token)
    ).json()
    assert medications[0]["status"] == "discontinued"


def test_resolve_discrepancy_dismiss_leaves_medication_list_unchanged(client):
    token = _register_and_login(client, "resolvedismiss@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    discrepancy = _get_discrepancies(client, token, patient["id"], analysis_id)[0]

    response = _resolve(
        client,
        token,
        patient["id"],
        analysis_id,
        discrepancy["id"],
        {"action": "dismiss", "note": "Not clinically relevant."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resolution_status"] == "dismissed"
    assert body["resolution_action"] == "dismiss"
    assert body["medication_id"] is None

    medications = client.get(
        f"/patients/{patient['id']}/medications", headers=_auth_headers(token)
    ).json()
    assert medications == []


def test_resolve_discrepancy_response_includes_audit_trail(client):
    token = _register_and_login(client, "resolveaudit@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    discrepancy = _get_discrepancies(client, token, patient["id"], analysis_id)[0]

    response = _resolve(
        client,
        token,
        patient["id"],
        analysis_id,
        discrepancy["id"],
        {
            "action": "add_medication",
            "medication_name": "Lisinopril",
            "dose": "10 mg",
            "route": "oral",
            "frequency": "once daily",
            "status": "active",
            "note": "Confirmed by phone.",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["resolved_at"] is not None
    assert body["resolution_note"] == "Confirmed by phone."
    assert body["resolved_by"]["email"] == "resolveaudit@example.com"
    assert body["resolved_by"]["name"] == "AI Test User"


def test_resolve_discrepancy_preserves_original_finding_after_resolving(client):
    # "The analysis should remain a permanent record": resolving must not
    # erase what the reconciliation engine originally found.
    token = _register_and_login(client, "resolvepreserve@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    discrepancy = _get_discrepancies(client, token, patient["id"], analysis_id)[0]
    original_title = discrepancy["title"]
    original_mention_id = discrepancy["medication_mention_id"]

    _resolve(
        client,
        token,
        patient["id"],
        analysis_id,
        discrepancy["id"],
        {"action": "dismiss"},
    )

    refetched = _get_discrepancies(client, token, patient["id"], analysis_id)[0]
    assert refetched["title"] == original_title
    assert refetched["medication_mention_id"] == original_mention_id
    assert refetched["resolution_status"] == "dismissed"


def test_resolve_discrepancy_resolved_state_persists_after_refresh(client):
    token = _register_and_login(client, "resolvepersists@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    discrepancy = _get_discrepancies(client, token, patient["id"], analysis_id)[0]

    _resolve(client, token, patient["id"], analysis_id, discrepancy["id"], {"action": "dismiss"})

    # A second, independent GET (simulating a page refresh) must reflect it.
    refetched = _get_discrepancies(client, token, patient["id"], analysis_id)[0]
    assert refetched["resolution_status"] == "dismissed"


def test_resolve_discrepancy_rejects_resolving_twice(client):
    token = _register_and_login(client, "resolvetwiceroute@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    discrepancy = _get_discrepancies(client, token, patient["id"], analysis_id)[0]

    first = _resolve(
        client, token, patient["id"], analysis_id, discrepancy["id"], {"action": "dismiss"}
    )
    assert first.status_code == 200

    second = _resolve(
        client, token, patient["id"], analysis_id, discrepancy["id"], {"action": "dismiss"}
    )
    assert second.status_code == 409


def test_resolve_discrepancy_rejects_action_invalid_for_discrepancy_type(client):
    token = _register_and_login(client, "resolveinvalidaction@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    discrepancy = _get_discrepancies(client, token, patient["id"], analysis_id)[0]
    assert discrepancy["discrepancy_type"] == "missing_from_medication_list"

    # update_medication doesn't make sense here; there's no medication yet.
    response = _resolve(
        client,
        token,
        patient["id"],
        analysis_id,
        discrepancy["id"],
        {"action": "update_medication", "dose": "10 mg"},
    )

    assert response.status_code == 400


def test_resolve_discrepancy_rejects_extra_fields(client):
    token = _register_and_login(client, "resolveextrafields@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])
    discrepancy = _get_discrepancies(client, token, patient["id"], analysis_id)[0]

    response = _resolve(
        client,
        token,
        patient["id"],
        analysis_id,
        discrepancy["id"],
        {"action": "dismiss", "unexpected_field": "nope"},
    )

    assert response.status_code == 422


def test_resolve_discrepancy_requires_authentication(client):
    response = client.post(
        "/patients/1/analyses/1/discrepancies/1/resolve", json={"action": "dismiss"}
    )
    assert response.status_code == 401


def test_resolve_discrepancy_returns_404_for_another_users_patient(client):
    token_a = _register_and_login(client, "resolveownera@example.com")
    token_b = _register_and_login(client, "resolveownerb@example.com")
    patient = _create_patient(client, token_a).json()
    document = _create_document(client, token_a, patient["id"])
    analysis_id = _create_completed_analysis(client, token_a, patient["id"], document["id"])
    discrepancy = _get_discrepancies(client, token_a, patient["id"], analysis_id)[0]

    response = _resolve(
        client, token_b, patient["id"], analysis_id, discrepancy["id"], {"action": "dismiss"}
    )

    assert response.status_code == 404


def test_resolve_discrepancy_returns_404_for_unknown_analysis(client):
    token = _register_and_login(client, "resolveunknownanalysis@example.com")
    patient = _create_patient(client, token).json()

    response = _resolve(client, token, patient["id"], 999999, 1, {"action": "dismiss"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis not found"


def test_resolve_discrepancy_returns_404_for_unknown_discrepancy(client):
    token = _register_and_login(client, "resolveunknowndiscrepancy@example.com")
    patient = _create_patient(client, token).json()
    document = _create_document(client, token, patient["id"])
    analysis_id = _create_completed_analysis(client, token, patient["id"], document["id"])

    response = _resolve(client, token, patient["id"], analysis_id, 999999, {"action": "dismiss"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Discrepancy not found"


def test_resolve_discrepancy_returns_404_for_discrepancy_belonging_to_a_different_analysis(client):
    token = _register_and_login(client, "resolvewronganalysis@example.com")
    patient = _create_patient(client, token).json()
    document_a = _create_document(client, token, patient["id"])
    document_b = _create_document(client, token, patient["id"])
    analysis_a_id = _create_completed_analysis(client, token, patient["id"], document_a["id"])
    analysis_b_id = _create_completed_analysis(client, token, patient["id"], document_b["id"])
    discrepancy_a = _get_discrepancies(client, token, patient["id"], analysis_a_id)[0]

    response = _resolve(
        client, token, patient["id"], analysis_b_id, discrepancy_a["id"], {"action": "dismiss"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Discrepancy not found"


def test_resolve_discrepancy_handles_multiple_discrepancies_independently(client):
    token = _register_and_login(client, "resolvemultiple@example.com")
    patient = _create_patient(client, token).json()
    _create_medication(client, token, patient["id"], dose="20 mg")
    document = _create_document(client, token, patient["id"])
    response_text = json.dumps(
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
            "possible_inconsistencies": [],
            "summary": "Two medications noted.",
        }
    )
    analysis_id = _create_completed_analysis(
        client, token, patient["id"], document["id"], response_text=response_text
    )
    discrepancies = _get_discrepancies(client, token, patient["id"], analysis_id)
    assert len(discrepancies) == 2
    by_type = {d["discrepancy_type"]: d for d in discrepancies}
    dose_conflict = by_type["dose_conflict"]
    missing = by_type["missing_from_medication_list"]

    resolve_response = _resolve(
        client,
        token,
        patient["id"],
        analysis_id,
        dose_conflict["id"],
        {"action": "update_medication", "dose": "10 mg"},
    )
    assert resolve_response.status_code == 200

    refetched = _get_discrepancies(client, token, patient["id"], analysis_id)
    by_type_after = {d["discrepancy_type"]: d for d in refetched}
    assert by_type_after["dose_conflict"]["resolution_status"] == "resolved"
    # The Metformin discrepancy was never touched; still open.
    assert by_type_after["missing_from_medication_list"]["resolution_status"] == "open"
    assert by_type_after["missing_from_medication_list"]["id"] == missing["id"]
