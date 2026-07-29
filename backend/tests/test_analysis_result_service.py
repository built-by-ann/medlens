from datetime import date

import pytest

from app.ai.schemas import ClinicalSummary
from app.core.security import hash_password
from app.models.analysis import Analysis
from app.models.analysis_inconsistency import AnalysisInconsistency
from app.models.analysis_medication_mention import AnalysisMedicationMention
from app.models.clinical_document import ClinicalDocument
from app.models.patient import Patient
from app.models.user import User
from app.schemas.analysis import AnalysisCreate
from app.services.analysis_result_service import persist_analysis_result
from app.services.analysis_service import create_analysis


def _create_user(db, email="result.user@example.com"):
    user = User(
        email=email,
        hashed_password=hash_password("correcthorse123"),
        name="Result User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _create_patient(db, user, **overrides):
    defaults = {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": date(1980, 5, 14),
        "status": "active",
    }
    defaults.update(overrides)

    patient = Patient(user_id=user.id, **defaults)
    db.add(patient)
    db.commit()
    db.refresh(patient)

    return patient


def _create_clinical_document(db, patient):
    document = ClinicalDocument(
        patient_id=patient.id,
        user_id=patient.user_id,
        document_type="visit_note",
        title="Visit Note",
        raw_text="Patient takes Lisinopril 10 mg oral once daily.",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _create_pending_analysis(db, email):
    user = _create_user(db, email=email)
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)

    return create_analysis(db, patient, AnalysisCreate(clinical_document_ids=[document.id]))


def _clinical_summary(**overrides):
    payload = {
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
    payload.update(overrides)

    return ClinicalSummary.model_validate(payload)


def test_persist_analysis_result_succeeds(db):
    analysis = _create_pending_analysis(db, "persistsuccess@example.com")

    updated = persist_analysis_result(
        db, analysis, _clinical_summary(), provider="gemini", model="gemini-2.0-flash"
    )

    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.provider == "gemini"
    assert updated.model_name == "gemini-2.0-flash"
    assert updated.summary == "Patient is on Lisinopril 10 mg once daily."
    assert updated.total_findings == 0
    assert updated.high_severity_findings == 0
    assert updated.medium_severity_findings == 0
    assert updated.low_severity_findings == 0

    mentions = (
        db.query(AnalysisMedicationMention)
        .filter(AnalysisMedicationMention.analysis_id == analysis.id)
        .all()
    )
    assert len(mentions) == 1
    assert mentions[0].medication_name == "Lisinopril"
    assert mentions[0].dosage == "10 mg"
    assert mentions[0].route == "oral"
    assert mentions[0].frequency == "once daily"
    assert mentions[0].status == "active"
    assert mentions[0].notes is None

    inconsistencies = (
        db.query(AnalysisInconsistency)
        .filter(AnalysisInconsistency.analysis_id == analysis.id)
        .all()
    )
    assert len(inconsistencies) == 1
    assert inconsistencies[0].description == "Dose differs between two notes."


def test_persist_analysis_result_handles_multiple_medications(db):
    analysis = _create_pending_analysis(db, "multiplemedications@example.com")

    summary = _clinical_summary(
        medications=[
            {"name": "Lisinopril", "dosage": "10 mg"},
            {"name": "Metformin", "dosage": "500 mg"},
            {"name": "Atorvastatin", "dosage": "20 mg"},
        ]
    )

    persist_analysis_result(db, analysis, summary, provider="gemini", model="gemini-2.0-flash")

    mentions = (
        db.query(AnalysisMedicationMention)
        .filter(AnalysisMedicationMention.analysis_id == analysis.id)
        .all()
    )
    assert {mention.medication_name for mention in mentions} == {
        "Lisinopril",
        "Metformin",
        "Atorvastatin",
    }


def test_persist_analysis_result_handles_multiple_inconsistencies(db):
    analysis = _create_pending_analysis(db, "multipleinconsistencies@example.com")

    summary = _clinical_summary(
        possible_inconsistencies=[
            "Dose differs between two notes.",
            "Status is unclear in one note.",
            "Frequency conflicts across notes.",
        ]
    )

    persist_analysis_result(db, analysis, summary, provider="gemini", model="gemini-2.0-flash")

    inconsistencies = (
        db.query(AnalysisInconsistency)
        .filter(AnalysisInconsistency.analysis_id == analysis.id)
        .all()
    )
    assert {row.description for row in inconsistencies} == {
        "Dose differs between two notes.",
        "Status is unclear in one note.",
        "Frequency conflicts across notes.",
    }


def test_persist_analysis_result_handles_empty_medication_list(db):
    analysis = _create_pending_analysis(db, "emptymedications@example.com")

    summary = _clinical_summary(medications=[])

    updated = persist_analysis_result(
        db, analysis, summary, provider="gemini", model="gemini-2.0-flash"
    )

    assert updated.status == "completed"
    assert (
        db.query(AnalysisMedicationMention)
        .filter(AnalysisMedicationMention.analysis_id == analysis.id)
        .count()
        == 0
    )


def test_persist_analysis_result_handles_empty_inconsistency_list(db):
    analysis = _create_pending_analysis(db, "emptyinconsistencies@example.com")

    summary = _clinical_summary(possible_inconsistencies=[])

    updated = persist_analysis_result(
        db, analysis, summary, provider="gemini", model="gemini-2.0-flash"
    )

    assert updated.status == "completed"
    assert (
        db.query(AnalysisInconsistency)
        .filter(AnalysisInconsistency.analysis_id == analysis.id)
        .count()
        == 0
    )


def test_persist_analysis_result_rolls_back_when_completion_fails(db, monkeypatch):
    analysis = _create_pending_analysis(db, "rollback@example.com")
    analysis_id = analysis.id

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure during completion")

    monkeypatch.setattr(
        "app.services.analysis_result_service.mark_analysis_completed", _boom
    )

    with pytest.raises(RuntimeError):
        persist_analysis_result(
            db, analysis, _clinical_summary(), provider="gemini", model="gemini-2.0-flash"
        )

    db.rollback()

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

    reloaded = db.get(Analysis, analysis_id)
    assert reloaded.status == "pending"
