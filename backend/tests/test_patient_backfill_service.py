from datetime import date

import pytest

from app.models.analysis import Analysis
from app.models.clinical_document import ClinicalDocument
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.user import User
from app.services.patient_backfill_service import (
    LEGACY_PATIENT_DATE_OF_BIRTH,
    LEGACY_PATIENT_FIRST_NAME,
    LEGACY_PATIENT_LAST_NAME,
    LEGACY_PATIENT_NOTES,
    AmbiguousPatientBackfillError,
    backfill_patient_ids,
    clear_patient_ids,
)


def _make_user(db, email) -> User:
    user = User(email=email, hashed_password="hashed")
    db.add(user)
    db.flush()
    return user


def _make_patient(db, user_id, **overrides) -> Patient:
    defaults = {
        "first_name": "Jane",
        "last_name": "Doe",
        "date_of_birth": date(1980, 5, 14),
        "status": "active",
    }
    defaults.update(overrides)
    patient = Patient(user_id=user_id, **defaults)
    db.add(patient)
    db.flush()
    return patient


def _make_medication(db, user_id, patient_id=None) -> Medication:
    medication = Medication(
        user_id=user_id,
        patient_id=patient_id,
        medication_name="Lisinopril",
        dose="10 mg",
        route="oral",
        frequency="once daily",
        status="active",
        source="patient_reported",
    )
    db.add(medication)
    db.flush()
    return medication


def _make_document(db, user_id, patient_id=None) -> ClinicalDocument:
    document = ClinicalDocument(
        user_id=user_id,
        patient_id=patient_id,
        document_type="visit_note",
        title="Visit note",
        raw_text="Patient doing well.",
    )
    db.add(document)
    db.flush()
    return document


def _make_analysis(db, user_id, patient_id=None) -> Analysis:
    analysis = Analysis(user_id=user_id, patient_id=patient_id, status="completed")
    db.add(analysis)
    db.flush()
    return analysis


def test_backfill_assigns_legacy_resources_to_sole_active_patient(db):
    user = _make_user(db, "single-patient@example.com")
    patient = _make_patient(db, user.id)
    medication = _make_medication(db, user.id)
    document = _make_document(db, user.id)
    analysis = _make_analysis(db, user.id)
    db.commit()

    backfill_patient_ids(db)
    db.commit()

    db.refresh(medication)
    db.refresh(document)
    db.refresh(analysis)

    assert medication.patient_id == patient.id
    assert document.patient_id == patient.id
    assert analysis.patient_id == patient.id

    # No extra patient was created.
    assert db.query(Patient).filter(Patient.user_id == user.id).count() == 1


def test_backfill_ignores_archived_patients_when_counting(db):
    user = _make_user(db, "archived-only@example.com")
    _make_patient(db, user.id, status="archived")
    medication = _make_medication(db, user.id)
    db.commit()

    backfill_patient_ids(db)
    db.commit()

    db.refresh(medication)
    patients = db.query(Patient).filter(Patient.user_id == user.id).all()

    # The archived patient doesn't count as "existing", so a placeholder is
    # created instead of attaching the legacy medication to it.
    assert len(patients) == 2
    created = next(p for p in patients if p.status == "active")
    assert medication.patient_id == created.id
    assert created.first_name == LEGACY_PATIENT_FIRST_NAME


def test_backfill_creates_placeholder_patient_with_expected_fields(db):
    user = _make_user(db, "no-patient@example.com")
    medication = _make_medication(db, user.id)
    db.commit()

    backfill_patient_ids(db)
    db.commit()

    db.refresh(medication)
    patient = db.query(Patient).filter(Patient.id == medication.patient_id).one()

    assert patient.user_id == user.id
    assert patient.first_name == LEGACY_PATIENT_FIRST_NAME
    assert patient.last_name == LEGACY_PATIENT_LAST_NAME
    assert patient.date_of_birth == LEGACY_PATIENT_DATE_OF_BIRTH
    assert patient.status == "active"
    assert patient.notes == LEGACY_PATIENT_NOTES
    assert patient.external_mrn is None


def test_backfill_does_not_touch_users_with_no_legacy_resources(db):
    user = _make_user(db, "untouched@example.com")
    _make_patient(db, user.id)
    _make_patient(db, user.id)  # two patients, but nothing to backfill
    db.commit()

    # Should not raise, since there is no legacy data needing a decision.
    backfill_patient_ids(db)
    db.commit()

    assert db.query(Patient).filter(Patient.user_id == user.id).count() == 2


def test_backfill_raises_for_multiple_active_patients_with_legacy_data(db):
    user = _make_user(db, "ambiguous@example.com")
    patient_a = _make_patient(db, user.id, first_name="A")
    patient_b = _make_patient(db, user.id, first_name="B")
    _make_medication(db, user.id)
    db.commit()

    with pytest.raises(AmbiguousPatientBackfillError) as excinfo:
        backfill_patient_ids(db)

    assert excinfo.value.user_id == user.id
    assert set(excinfo.value.active_patient_ids) == {patient_a.id, patient_b.id}


def test_rollback_after_failure_leaves_earlier_users_untouched(db):
    clean_user = _make_user(db, "clean@example.com")
    clean_patient = _make_patient(db, clean_user.id)
    clean_medication = _make_medication(db, clean_user.id)

    ambiguous_user = _make_user(db, "ambiguous2@example.com")
    _make_patient(db, ambiguous_user.id, first_name="A")
    _make_patient(db, ambiguous_user.id, first_name="B")
    _make_medication(db, ambiguous_user.id)
    db.commit()

    with pytest.raises(AmbiguousPatientBackfillError):
        backfill_patient_ids(db)

    # Whatever the function already flushed for clean_user before hitting
    # the ambiguous one is undone by rolling back the whole transaction -
    # exactly what Alembic's transactional DDL does automatically on a
    # real migration failure.
    db.rollback()

    db.refresh(clean_medication)
    assert clean_medication.patient_id is None
    assert db.query(Patient).filter(Patient.user_id == clean_user.id).count() == 1
    assert clean_patient.id is not None  # sanity: fixture data itself is intact


def test_backfill_is_idempotent(db):
    user = _make_user(db, "idempotent@example.com")
    medication = _make_medication(db, user.id)
    db.commit()

    backfill_patient_ids(db)
    db.commit()
    first_patient_id = db.query(Medication).filter(Medication.id == medication.id).one().patient_id

    backfill_patient_ids(db)
    db.commit()
    db.refresh(medication)

    assert medication.patient_id == first_patient_id
    assert db.query(Patient).filter(Patient.user_id == user.id).count() == 1


def test_backfill_leaves_no_orphaned_records(db):
    user = _make_user(db, "no-orphans@example.com")
    _make_medication(db, user.id)
    _make_document(db, user.id)
    _make_analysis(db, user.id)
    db.commit()

    backfill_patient_ids(db)
    db.commit()

    assert db.query(Medication).filter(Medication.patient_id.is_(None)).count() == 0
    assert db.query(ClinicalDocument).filter(ClinicalDocument.patient_id.is_(None)).count() == 0
    assert db.query(Analysis).filter(Analysis.patient_id.is_(None)).count() == 0


def test_backfilled_ownership_is_consistent_between_patient_and_resource(db):
    user = _make_user(db, "consistent@example.com")
    medication = _make_medication(db, user.id)
    db.commit()

    backfill_patient_ids(db)
    db.commit()

    db.refresh(medication)
    patient = db.query(Patient).filter(Patient.id == medication.patient_id).one()

    assert patient.user_id == medication.user_id


def test_relationships_load_in_both_directions_after_backfill(db):
    user = _make_user(db, "relationships@example.com")
    patient = _make_patient(db, user.id)
    medication = _make_medication(db, user.id, patient_id=patient.id)
    document = _make_document(db, user.id, patient_id=patient.id)
    analysis = _make_analysis(db, user.id, patient_id=patient.id)
    db.commit()

    db.expire_all()
    reloaded_patient = db.query(Patient).filter(Patient.id == patient.id).one()

    assert [m.id for m in reloaded_patient.medications] == [medication.id]
    assert [d.id for d in reloaded_patient.clinical_documents] == [document.id]
    assert [a.id for a in reloaded_patient.analyses] == [analysis.id]

    reloaded_medication = db.query(Medication).filter(Medication.id == medication.id).one()
    assert reloaded_medication.patient.id == patient.id
    # The old ownership path still works side by side with the new one.
    assert reloaded_medication.user.id == user.id


def test_clear_patient_ids_nulls_out_without_deleting_placeholder_patient(db):
    user = _make_user(db, "clear@example.com")
    medication = _make_medication(db, user.id)
    db.commit()

    backfill_patient_ids(db)
    db.commit()
    placeholder_patient_id = db.query(Medication).filter(Medication.id == medication.id).one().patient_id

    clear_patient_ids(db)
    db.commit()

    db.refresh(medication)
    assert medication.patient_id is None
    # The placeholder patient row itself is left in place.
    assert db.query(Patient).filter(Patient.id == placeholder_patient_id).count() == 1


def test_medication_api_still_works_alongside_the_backfill_service(client, db):
    # Regression check: creating/listing medications keeps working
    # correctly for a freshly created patient, independent of whatever the
    # backfill migration did elsewhere. As of Issue #129, medications are
    # patient-scoped (see tests/test_medications.py for the full contract
    # test suite) - this only checks the two aren't stepping on each other.
    register_response = client.post(
        "/auth/register",
        json={"email": "legacy-api@example.com", "password": "correcthorse123", "name": "Legacy"},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": "legacy-api@example.com", "password": "correcthorse123"},
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    patient_response = client.post(
        "/patients",
        json={"first_name": "Jane", "last_name": "Doe", "date_of_birth": "1980-05-14"},
        headers=headers,
    )
    patient_id = patient_response.json()["id"]

    create_response = client.post(
        f"/patients/{patient_id}/medications",
        json={
            "medication_name": "Lisinopril",
            "dose": "10 mg",
            "route": "oral",
            "frequency": "once daily",
            "status": "active",
            "source": "patient_reported",
        },
        headers=headers,
    )
    assert create_response.status_code == 201
    assert create_response.json()["patient_id"] == patient_id

    list_response = client.get(f"/patients/{patient_id}/medications", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()[0]["patient_id"] == patient_id
