from datetime import date

import pytest

from app.ai.schemas import ClinicalSummary
from app.core.security import hash_password
from app.models.analysis import Analysis
from app.models.analysis_inconsistency import AnalysisInconsistency
from app.models.analysis_medication_mention import AnalysisMedicationMention
from app.models.clinical_document import ClinicalDocument
from app.models.medication import Medication
from app.models.medication_discrepancy import MedicationDiscrepancy
from app.models.medication_mention import MedicationMention
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


def _create_clinical_document(db, patient, **overrides):
    defaults = {
        "document_type": "visit_note",
        "title": "Visit Note",
        "raw_text": "Patient takes Lisinopril 10 mg oral once daily.",
    }
    defaults.update(overrides)

    document = ClinicalDocument(patient_id=patient.id, **defaults)
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _create_pending_analysis(db, email):
    _, analysis = _create_pending_analysis_with_patient(db, email)

    return analysis


def _create_pending_analysis_with_patient(db, email):
    user = _create_user(db, email=email)
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)

    analysis = create_analysis(db, patient, AnalysisCreate(clinical_document_ids=[document.id]))

    return patient, analysis


def _create_medication(db, patient, **overrides):
    defaults = {
        "medication_name": "Lisinopril",
        "dose": "10 mg",
        "route": "oral",
        "frequency": "once daily",
        "status": "active",
        "source": "patient_reported",
    }
    defaults.update(overrides)

    medication = Medication(patient_id=patient.id, **defaults)
    db.add(medication)
    db.commit()
    db.refresh(medication)

    return medication


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
    # This patient has no Medication rows at all (see _create_pending_analysis),
    # so the AI-extracted Lisinopril mention is necessarily "missing from the
    # medication list" - Issue #148's reconciliation integration means this
    # is no longer a hardcoded zero.
    analysis = _create_pending_analysis(db, "persistsuccess@example.com")

    updated = persist_analysis_result(
        db, analysis, _clinical_summary(), provider="gemini", model="gemini-2.0-flash"
    )

    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.provider == "gemini"
    assert updated.model_name == "gemini-2.0-flash"
    assert updated.summary == "Patient is on Lisinopril 10 mg once daily."
    assert updated.total_findings == 1
    assert updated.high_severity_findings == 1
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
    # Issue #148: reconciliation's own writes (the bridged MedicationMention
    # and any MedicationDiscrepancy it produced) ride in the same
    # transaction, so they roll back too - no partially persisted
    # discrepancies are left behind.
    assert db.query(MedicationMention).count() == 0
    assert (
        db.query(MedicationDiscrepancy)
        .filter(MedicationDiscrepancy.analysis_id == analysis_id)
        .count()
        == 0
    )

    reloaded = db.get(Analysis, analysis_id)
    assert reloaded.status == "pending"


def test_persist_analysis_result_creates_no_discrepancy_when_ai_medication_matches_list(db):
    patient, analysis = _create_pending_analysis_with_patient(db, "matchinglist@example.com")
    _create_medication(db, patient, medication_name="Lisinopril", dose="10 mg")

    updated = persist_analysis_result(
        db, analysis, _clinical_summary(), provider="gemini", model="gemini-2.0-flash"
    )

    assert updated.total_findings == 0

    mention = db.query(MedicationMention).filter(MedicationMention.medication_name == "Lisinopril").one()
    assert mention.clinical_document_id in {document.id for document in analysis.clinical_documents}
    assert mention.dose == "10 mg"
    assert mention.route == "oral"
    assert mention.frequency == "once daily"
    assert mention.status == "active"

    assert (
        db.query(MedicationDiscrepancy)
        .filter(MedicationDiscrepancy.analysis_id == analysis.id)
        .count()
        == 0
    )


def test_persist_analysis_result_creates_discrepancy_with_evidence_when_dose_conflicts(db):
    patient, analysis = _create_pending_analysis_with_patient(db, "doseconflict@example.com")
    medication = _create_medication(db, patient, medication_name="Lisinopril", dose="10 mg")

    summary = _clinical_summary(
        medications=[
            {
                "name": "Lisinopril",
                "dosage": "20 mg",
                "route": "oral",
                "frequency": "once daily",
                "status": "active",
                "notes": None,
            }
        ]
    )

    updated = persist_analysis_result(
        db, analysis, summary, provider="gemini", model="gemini-2.0-flash"
    )

    assert updated.total_findings == 1
    assert updated.medium_severity_findings == 1

    discrepancy = (
        db.query(MedicationDiscrepancy)
        .filter(MedicationDiscrepancy.analysis_id == analysis.id)
        .one()
    )
    assert discrepancy.discrepancy_type == "dose_conflict"
    assert discrepancy.medication_id == medication.id
    assert discrepancy.expected_value == "10 mg"
    assert discrepancy.observed_value == "20 mg"

    # Supporting evidence: the discrepancy's medication_mention_id resolves
    # to a real, persisted MedicationMention tied to one of this analysis's
    # own clinical documents.
    mention = db.get(MedicationMention, discrepancy.medication_mention_id)
    assert mention is not None
    assert mention.medication_name == "Lisinopril"
    assert mention.dose == "20 mg"
    assert mention.clinical_document_id in {document.id for document in analysis.clinical_documents}


def test_persist_analysis_result_does_not_duplicate_discrepancies_for_repeated_mentions(db):
    # Two AI-extracted entries for the same medication (as could happen when
    # it is mentioned with different details across the combined notes) -
    # reconciliation still produces exactly one finding, not one per mention.
    analysis = _create_pending_analysis(db, "repeatedmentions@example.com")

    summary = _clinical_summary(
        medications=[
            {"name": "Lisinopril", "dosage": "10 mg"},
            {"name": "Lisinopril", "dosage": "20 mg"},
        ]
    )

    updated = persist_analysis_result(
        db, analysis, summary, provider="gemini", model="gemini-2.0-flash"
    )

    assert updated.total_findings == 1
    assert db.query(MedicationMention).count() == 2
    assert (
        db.query(MedicationDiscrepancy)
        .filter(MedicationDiscrepancy.analysis_id == analysis.id)
        .count()
        == 1
    )


def test_persist_analysis_result_attributes_each_medication_to_its_true_source_document(db):
    # Issue #152: a genuinely multi-document analysis, where two different
    # medications are each mentioned in a different one of the two selected
    # documents - the case the earlier lowest-id placeholder could never
    # represent correctly (both would have landed on document_a regardless).
    user = _create_user(db, "trueprovenance@example.com")
    patient = _create_patient(db, user)
    document_a = _create_clinical_document(db, patient, title="Visit Note")
    document_b = _create_clinical_document(
        db, patient, title="Discharge Summary", raw_text="Patient takes Metformin 500 mg."
    )
    analysis = create_analysis(
        db, patient, AnalysisCreate(clinical_document_ids=[document_a.id, document_b.id])
    )

    summary = _clinical_summary(
        medications=[
            {"name": "Lisinopril", "dosage": "10 mg", "source_note": 1},
            {"name": "Metformin", "dosage": "500 mg", "source_note": 2},
        ]
    )

    persist_analysis_result(db, analysis, summary, provider="gemini", model="gemini-2.0-flash")

    lisinopril = db.query(MedicationMention).filter_by(medication_name="Lisinopril").one()
    metformin = db.query(MedicationMention).filter_by(medication_name="Metformin").one()
    assert lisinopril.clinical_document_id == document_a.id
    assert metformin.clinical_document_id == document_b.id


def test_persist_analysis_result_attributes_a_repeated_medication_to_each_of_its_documents(db):
    # The same medication mentioned in both selected documents becomes two
    # separate MedicationMention rows, each tied to its own real source
    # document, rather than one mention (or two mentions collapsed onto a
    # single document).
    user = _create_user(db, "repeatedacrossdocs@example.com")
    patient = _create_patient(db, user)
    document_a = _create_clinical_document(db, patient, title="Visit Note")
    document_b = _create_clinical_document(
        db, patient, title="Follow-up Note", raw_text="Lisinopril increased to 20 mg."
    )
    analysis = create_analysis(
        db, patient, AnalysisCreate(clinical_document_ids=[document_a.id, document_b.id])
    )

    summary = _clinical_summary(
        medications=[
            {"name": "Lisinopril", "dosage": "10 mg", "source_note": 1},
            {"name": "Lisinopril", "dosage": "20 mg", "source_note": 2},
        ]
    )

    persist_analysis_result(db, analysis, summary, provider="gemini", model="gemini-2.0-flash")

    mentions_by_dose = {
        mention.dose: mention.clinical_document_id
        for mention in db.query(MedicationMention).filter_by(medication_name="Lisinopril").all()
    }
    assert mentions_by_dose == {"10 mg": document_a.id, "20 mg": document_b.id}
