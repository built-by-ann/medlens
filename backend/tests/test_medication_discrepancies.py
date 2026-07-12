import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.models.analysis import Analysis
from app.models.clinical_document import ClinicalDocument
from app.models.medication import Medication
from app.models.medication_discrepancy import MedicationDiscrepancy
from app.models.medication_mention import MedicationMention
from app.models.user import User
from app.schemas.medication_discrepancy import (
    DiscrepancySeverity,
    DiscrepancyType,
    MedicationDiscrepancyCreate,
    MedicationDiscrepancyResponse,
    ResolutionStatus,
)
from app.services.medication_discrepancy_service import create_medication_discrepancy


def _create_user(db, email="finding.user@example.com"):
    user = User(
        email=email,
        hashed_password=hash_password("correcthorse123"),
        name="Finding User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _create_analysis(db, user):
    analysis = Analysis(user_id=user.id, status="processing")
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    return analysis


def _create_clinical_document(db, user):
    document = ClinicalDocument(
        user_id=user.id,
        document_type="visit_note",
        title="Visit Note",
        raw_text="Patient takes Lisinopril 10 mg oral once daily.",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _create_medication(db, user):
    medication = Medication(
        user_id=user.id,
        medication_name="Lisinopril",
        dose="10 mg",
        route="oral",
        frequency="once daily",
        status="active",
        source="patient_reported",
    )
    db.add(medication)
    db.commit()
    db.refresh(medication)

    return medication


def _create_medication_mention(db, document):
    mention = MedicationMention(
        clinical_document_id=document.id,
        medication_name="Lisinopril",
        dose="10 mg",
        route="oral",
        frequency="once daily",
        status="discontinued",
    )
    db.add(mention)
    db.commit()
    db.refresh(mention)

    return mention


def _build_discrepancy_in(**overrides):
    payload = {
        "discrepancy_type": DiscrepancyType.STATUS_CONFLICT,
        "severity": DiscrepancySeverity.HIGH,
        "title": "Lisinopril status conflict",
        "ai_explanation": (
            "Marked active in the medication list but discontinued in a visit note."
        ),
        "recommendation": "Confirm current status with the patient.",
        "expected_value": "active",
        "observed_value": "discontinued",
    }
    payload.update(overrides)

    return MedicationDiscrepancyCreate(**payload)


def test_create_medication_discrepancy_succeeds(db):
    user = _create_user(db)
    analysis = _create_analysis(db, user)
    medication = _create_medication(db, user)
    document = _create_clinical_document(db, user)
    mention = _create_medication_mention(db, document)

    discrepancy_in = _build_discrepancy_in(
        medication_id=medication.id, medication_mention_id=mention.id
    )

    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)

    assert discrepancy.id is not None
    assert discrepancy.analysis_id == analysis.id
    assert discrepancy.medication_id == medication.id
    assert discrepancy.medication_mention_id == mention.id
    assert discrepancy.discrepancy_type == "status_conflict"
    assert discrepancy.severity == "high"
    assert discrepancy.title == "Lisinopril status conflict"
    assert discrepancy.expected_value == "active"
    assert discrepancy.observed_value == "discontinued"
    assert discrepancy.resolution_status == "open"


@pytest.mark.parametrize("discrepancy_type", list(DiscrepancyType))
def test_create_medication_discrepancy_allows_each_finding_type(db, discrepancy_type):
    user = _create_user(db, email=f"type.{discrepancy_type.value}@example.com")
    analysis = _create_analysis(db, user)

    discrepancy_in = _build_discrepancy_in(discrepancy_type=discrepancy_type)
    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)

    assert discrepancy.discrepancy_type == discrepancy_type.value


@pytest.mark.parametrize("severity", list(DiscrepancySeverity))
def test_create_medication_discrepancy_allows_each_severity(db, severity):
    user = _create_user(db, email=f"severity.{severity.value}@example.com")
    analysis = _create_analysis(db, user)

    discrepancy_in = _build_discrepancy_in(severity=severity)
    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)

    assert discrepancy.severity == severity.value


@pytest.mark.parametrize("resolution_status", list(ResolutionStatus))
def test_create_medication_discrepancy_allows_each_resolution_status(
    db, resolution_status
):
    user = _create_user(db, email=f"resolution.{resolution_status.value}@example.com")
    analysis = _create_analysis(db, user)

    discrepancy_in = _build_discrepancy_in(resolution_status=resolution_status)
    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)

    assert discrepancy.resolution_status == resolution_status.value


def test_medication_discrepancy_create_rejects_invalid_discrepancy_type():
    with pytest.raises(ValidationError):
        _build_discrepancy_in(discrepancy_type="not_a_real_type")


def test_medication_discrepancy_create_rejects_invalid_severity():
    with pytest.raises(ValidationError):
        _build_discrepancy_in(severity="critical")


def test_medication_discrepancy_create_rejects_invalid_resolution_status():
    with pytest.raises(ValidationError):
        _build_discrepancy_in(resolution_status="closed")


def test_create_medication_discrepancy_allows_null_medication_id(db):
    user = _create_user(db, email="nullmedication@example.com")
    analysis = _create_analysis(db, user)
    document = _create_clinical_document(db, user)
    mention = _create_medication_mention(db, document)

    discrepancy_in = _build_discrepancy_in(
        discrepancy_type=DiscrepancyType.UNSUPPORTED_MEDICATION_LIST_ENTRY,
        medication_mention_id=mention.id,
    )
    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)

    assert discrepancy.medication_id is None
    assert discrepancy.medication_mention_id == mention.id


def test_create_medication_discrepancy_allows_null_medication_mention_id(db):
    user = _create_user(db, email="nullmention@example.com")
    analysis = _create_analysis(db, user)
    medication = _create_medication(db, user)

    discrepancy_in = _build_discrepancy_in(
        discrepancy_type=DiscrepancyType.MISSING_FROM_MEDICATION_LIST,
        medication_id=medication.id,
    )
    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)

    assert discrepancy.medication_mention_id is None
    assert discrepancy.medication_id == medication.id


def test_medication_discrepancy_relationship_to_analysis(db):
    user = _create_user(db, email="relanalysis@example.com")
    analysis = _create_analysis(db, user)

    discrepancy = create_medication_discrepancy(db, analysis.id, _build_discrepancy_in())

    db.refresh(analysis)
    assert discrepancy.analysis.id == analysis.id
    assert discrepancy in analysis.medication_discrepancies


def test_medication_discrepancy_relationship_to_medication(db):
    user = _create_user(db, email="relmedication@example.com")
    analysis = _create_analysis(db, user)
    medication = _create_medication(db, user)

    discrepancy_in = _build_discrepancy_in(medication_id=medication.id)
    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)

    db.refresh(medication)
    assert discrepancy.medication.id == medication.id
    assert discrepancy in medication.discrepancies


def test_medication_discrepancy_relationship_to_medication_mention(db):
    user = _create_user(db, email="relmention@example.com")
    analysis = _create_analysis(db, user)
    document = _create_clinical_document(db, user)
    mention = _create_medication_mention(db, document)

    discrepancy_in = _build_discrepancy_in(medication_mention_id=mention.id)
    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)

    db.refresh(mention)
    assert discrepancy.medication_mention.id == mention.id
    assert discrepancy in mention.discrepancies


def test_medication_discrepancy_serializes_through_response_schema(db):
    user = _create_user(db, email="serialize@example.com")
    analysis = _create_analysis(db, user)
    medication = _create_medication(db, user)

    discrepancy_in = _build_discrepancy_in(medication_id=medication.id)
    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)

    response = MedicationDiscrepancyResponse.model_validate(discrepancy)

    assert response.id == discrepancy.id
    assert response.analysis_id == analysis.id
    assert response.medication_id == medication.id
    assert response.medication_mention_id is None
    assert response.discrepancy_type == DiscrepancyType.STATUS_CONFLICT
    assert response.severity == DiscrepancySeverity.HIGH
    assert response.resolution_status == ResolutionStatus.OPEN
    assert response.expected_value == "active"
    assert response.observed_value == "discontinued"


def test_medication_discrepancy_requires_analysis_id(db):
    discrepancy = MedicationDiscrepancy(
        analysis_id=None,
        discrepancy_type="status_conflict",
        severity="high",
        title="Missing analysis",
        resolution_status="open",
    )
    db.add(discrepancy)

    with pytest.raises(IntegrityError):
        db.commit()

    db.rollback()


def test_deleting_analysis_cascades_to_medication_discrepancies(db):
    user = _create_user(db, email="cascadeanalysis@example.com")
    analysis = _create_analysis(db, user)

    discrepancy = create_medication_discrepancy(db, analysis.id, _build_discrepancy_in())
    discrepancy_id = discrepancy.id

    db.delete(analysis)
    db.commit()

    remaining = db.get(MedicationDiscrepancy, discrepancy_id)
    assert remaining is None


def test_deleting_medication_sets_medication_id_null_on_discrepancy(db):
    user = _create_user(db, email="deletemedication@example.com")
    analysis = _create_analysis(db, user)
    medication = _create_medication(db, user)

    discrepancy_in = _build_discrepancy_in(medication_id=medication.id)
    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)
    discrepancy_id = discrepancy.id

    db.delete(medication)
    db.commit()

    remaining = db.get(MedicationDiscrepancy, discrepancy_id)
    assert remaining is not None
    assert remaining.medication_id is None


def test_deleting_medication_mention_sets_medication_mention_id_null_on_discrepancy(db):
    user = _create_user(db, email="deletemention@example.com")
    analysis = _create_analysis(db, user)
    document = _create_clinical_document(db, user)
    mention = _create_medication_mention(db, document)

    discrepancy_in = _build_discrepancy_in(medication_mention_id=mention.id)
    discrepancy = create_medication_discrepancy(db, analysis.id, discrepancy_in)
    discrepancy_id = discrepancy.id

    db.delete(mention)
    db.commit()

    remaining = db.get(MedicationDiscrepancy, discrepancy_id)
    assert remaining is not None
    assert remaining.medication_mention_id is None
