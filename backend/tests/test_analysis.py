import pytest
from pydantic import ValidationError

from app.core.security import hash_password
from app.models.analysis import Analysis
from app.models.clinical_document import ClinicalDocument
from app.models.medication_discrepancy import MedicationDiscrepancy
from app.models.user import User
from app.schemas.analysis import (
    AnalysisCompletedSummary,
    AnalysisCreate,
    AnalysisFailure,
    AnalysisResponse,
    AnalysisStatus,
)
from app.services.analysis_service import (
    InvalidClinicalDocumentIdsError,
    create_analysis,
    mark_analysis_completed,
    mark_analysis_failed,
    mark_analysis_processing,
)


def _create_user(db, email="analysis.user@example.com"):
    user = User(
        email=email,
        hashed_password=hash_password("correcthorse123"),
        name="Analysis User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _create_clinical_document(db, user, title="Visit Note"):
    document = ClinicalDocument(
        user_id=user.id,
        document_type="visit_note",
        title=title,
        raw_text="Patient takes Lisinopril 10 mg oral once daily.",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _completed_summary(**overrides):
    payload = {
        "summary": "Found 2 discrepancies.",
        "total_findings": 2,
        "high_severity_findings": 1,
        "medium_severity_findings": 1,
        "low_severity_findings": 0,
        "provider": "google",
        "model_name": "gemini-pro",
    }
    payload.update(overrides)

    return AnalysisCompletedSummary(**payload)


def test_create_analysis_succeeds(db):
    user = _create_user(db)
    document = _create_clinical_document(db, user)

    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    assert analysis.id is not None
    assert analysis.user_id == user.id
    assert analysis.status == "pending"
    assert analysis.total_findings == 0
    assert analysis.high_severity_findings == 0
    assert analysis.medium_severity_findings == 0
    assert analysis.low_severity_findings == 0
    assert analysis.started_at is None
    assert analysis.completed_at is None
    assert analysis.error_message is None
    assert analysis.provider is None
    assert analysis.model_name is None


def test_create_analysis_defaults_to_pending_status(db):
    user = _create_user(db, email="defaultstatus@example.com")
    document = _create_clinical_document(db, user)

    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    assert analysis.status == "pending"


def test_create_analysis_rejects_nonexistent_document_id(db):
    user = _create_user(db, email="nonexistentdoc@example.com")

    with pytest.raises(InvalidClinicalDocumentIdsError) as exc_info:
        create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[999999]))

    assert exc_info.value.invalid_ids == [999999]
    assert db.query(Analysis).filter(Analysis.user_id == user.id).count() == 0


def test_create_analysis_rejects_document_owned_by_another_user(db):
    owner = _create_user(db, email="realowner@example.com")
    other_user = _create_user(db, email="intruder@example.com")
    other_document = _create_clinical_document(db, other_user)

    with pytest.raises(InvalidClinicalDocumentIdsError) as exc_info:
        create_analysis(db, owner.id, AnalysisCreate(clinical_document_ids=[other_document.id]))

    assert exc_info.value.invalid_ids == [other_document.id]
    assert db.query(Analysis).filter(Analysis.user_id == owner.id).count() == 0


def test_create_analysis_rejects_mixed_valid_and_invalid_document_ids(db):
    owner = _create_user(db, email="mixedowner@example.com")
    other_user = _create_user(db, email="mixedintruder@example.com")
    owned_document = _create_clinical_document(db, owner)
    other_document = _create_clinical_document(db, other_user)

    with pytest.raises(InvalidClinicalDocumentIdsError) as exc_info:
        create_analysis(
            db,
            owner.id,
            AnalysisCreate(clinical_document_ids=[owned_document.id, other_document.id]),
        )

    assert exc_info.value.invalid_ids == [other_document.id]
    assert db.query(Analysis).filter(Analysis.user_id == owner.id).count() == 0


def test_create_analysis_handles_duplicate_document_ids_without_duplicate_links(db):
    user = _create_user(db, email="duplicateids@example.com")
    document = _create_clinical_document(db, user)

    analysis = create_analysis(
        db, user.id, AnalysisCreate(clinical_document_ids=[document.id, document.id])
    )

    assert len(analysis.clinical_documents) == 1
    assert analysis.clinical_documents[0].id == document.id


def test_analysis_create_rejects_empty_document_id_list():
    with pytest.raises(ValidationError):
        AnalysisCreate(clinical_document_ids=[])


@pytest.mark.parametrize("status", list(AnalysisStatus))
def test_analysis_response_allows_each_status_value(db, status):
    user = _create_user(db, email=f"status.{status.value}@example.com")
    analysis = Analysis(user_id=user.id, status=status.value)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    response = AnalysisResponse.model_validate(analysis)

    assert response.status == status


def test_analysis_response_rejects_invalid_status(db):
    user = _create_user(db, email="invalidstatus@example.com")
    analysis = Analysis(user_id=user.id, status="not_a_real_status")
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    with pytest.raises(ValidationError):
        AnalysisResponse.model_validate(analysis)


def test_analysis_completed_summary_rejects_negative_counts():
    with pytest.raises(ValidationError):
        _completed_summary(total_findings=-1)


def test_analysis_failure_schema_requires_error_message():
    with pytest.raises(ValidationError):
        AnalysisFailure(error_message="")


def test_analysis_relationship_to_user(db):
    user = _create_user(db, email="reluser@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    db.refresh(user)
    assert analysis.user.id == user.id
    assert analysis in user.analyses


def test_analysis_supports_multiple_clinical_documents(db):
    user = _create_user(db, email="multidoc@example.com")
    document_a = _create_clinical_document(db, user, title="Visit Note")
    document_b = _create_clinical_document(db, user, title="Medication List")

    analysis = create_analysis(
        db, user.id, AnalysisCreate(clinical_document_ids=[document_a.id, document_b.id])
    )

    assert {document.id for document in analysis.clinical_documents} == {
        document_a.id,
        document_b.id,
    }


def test_clinical_document_can_belong_to_multiple_analyses(db):
    user = _create_user(db, email="shareddoc@example.com")
    document = _create_clinical_document(db, user)

    analysis_a = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))
    analysis_b = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    db.refresh(document)
    assert {analysis.id for analysis in document.analyses} == {analysis_a.id, analysis_b.id}


def test_analysis_relationship_to_medication_discrepancy(db):
    user = _create_user(db, email="reldiscrepancy@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    discrepancy = MedicationDiscrepancy(
        analysis_id=analysis.id,
        discrepancy_type="status_conflict",
        severity="high",
        title="Test finding",
        resolution_status="open",
    )
    db.add(discrepancy)
    db.commit()

    db.refresh(analysis)
    assert discrepancy in analysis.medication_discrepancies


def test_deleting_analysis_cascades_to_discrepancies(db):
    user = _create_user(db, email="cascadedelete@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    discrepancy = MedicationDiscrepancy(
        analysis_id=analysis.id,
        discrepancy_type="status_conflict",
        severity="high",
        title="Test finding",
        resolution_status="open",
    )
    db.add(discrepancy)
    db.commit()
    discrepancy_id = discrepancy.id

    db.delete(analysis)
    db.commit()

    assert db.get(MedicationDiscrepancy, discrepancy_id) is None


def test_deleting_clinical_document_removes_association_but_keeps_analysis(db):
    user = _create_user(db, email="deletedoc@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))
    analysis_id = analysis.id

    db.delete(document)
    db.commit()

    remaining_analysis = db.get(Analysis, analysis_id)
    assert remaining_analysis is not None
    assert remaining_analysis.clinical_documents == []


def test_analysis_serializes_through_response_schema(db):
    user = _create_user(db, email="serializeanalysis@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    response = AnalysisResponse.model_validate(analysis)

    assert response.id == analysis.id
    assert response.user_id == user.id
    assert response.status == AnalysisStatus.PENDING
    assert response.started_at is None
    assert response.completed_at is None
    assert response.error_message is None
    assert response.total_findings == 0
    assert response.high_severity_findings == 0
    assert response.medium_severity_findings == 0
    assert response.low_severity_findings == 0
    assert response.provider is None
    assert response.model_name is None


def test_mark_analysis_processing_sets_status_and_started_at(db):
    user = _create_user(db, email="processing@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    updated = mark_analysis_processing(db, analysis)

    assert updated.status == "processing"
    assert updated.started_at is not None
    assert updated.completed_at is None


def test_mark_analysis_completed_sets_status_and_summary_fields(db):
    user = _create_user(db, email="completed@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))
    mark_analysis_processing(db, analysis)

    updated = mark_analysis_completed(db, analysis, _completed_summary())

    assert updated.status == "completed"
    assert updated.completed_at is not None
    assert updated.summary == "Found 2 discrepancies."
    assert updated.total_findings == 2
    assert updated.high_severity_findings == 1
    assert updated.medium_severity_findings == 1
    assert updated.low_severity_findings == 0
    assert updated.provider == "google"
    assert updated.model_name == "gemini-pro"
    assert updated.error_message is None


def test_mark_analysis_completed_clears_previous_error_message(db):
    user = _create_user(db, email="clearserror@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    mark_analysis_failed(db, analysis, "Temporary provider outage")
    assert analysis.error_message == "Temporary provider outage"

    updated = mark_analysis_completed(
        db,
        analysis,
        _completed_summary(
            summary=None,
            total_findings=0,
            high_severity_findings=0,
            medium_severity_findings=0,
            low_severity_findings=0,
        ),
    )

    assert updated.error_message is None
    assert updated.status == "completed"


def test_analysis_completed_summary_allows_missing_provider_and_model(db):
    user = _create_user(db, email="noprovidermodel@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    summary_in = _completed_summary(provider=None, model_name=None)
    updated = mark_analysis_completed(db, analysis, summary_in)

    assert updated.provider is None
    assert updated.model_name is None


def test_mark_analysis_failed_sets_status_and_error_message(db):
    user = _create_user(db, email="failed@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))
    mark_analysis_processing(db, analysis)

    updated = mark_analysis_failed(db, analysis, "AI provider timeout")

    assert updated.status == "failed"
    assert updated.completed_at is not None
    assert updated.error_message == "AI provider timeout"
    assert updated.total_findings == 0
    assert updated.high_severity_findings == 0
    assert updated.medium_severity_findings == 0
    assert updated.low_severity_findings == 0


def test_analysis_timestamps_progress_through_lifecycle(db):
    user = _create_user(db, email="timestamps@example.com")
    document = _create_clinical_document(db, user)
    analysis = create_analysis(db, user.id, AnalysisCreate(clinical_document_ids=[document.id]))

    assert analysis.started_at is None
    assert analysis.completed_at is None

    mark_analysis_processing(db, analysis)
    assert analysis.started_at is not None
    assert analysis.completed_at is None

    mark_analysis_completed(
        db,
        analysis,
        _completed_summary(
            summary=None,
            total_findings=0,
            high_severity_findings=0,
            medium_severity_findings=0,
            low_severity_findings=0,
        ),
    )
    assert analysis.completed_at is not None
    assert analysis.completed_at >= analysis.started_at
