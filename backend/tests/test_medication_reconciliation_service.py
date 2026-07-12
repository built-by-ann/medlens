import pytest

from app.core.security import hash_password
from app.models.analysis import Analysis
from app.models.clinical_document import ClinicalDocument
from app.models.medication import Medication
from app.models.medication_discrepancy import MedicationDiscrepancy
from app.models.medication_mention import MedicationMention
from app.models.user import User
from app.schemas.analysis import AnalysisResponse, AnalysisStatus
from app.schemas.medication_discrepancy import (
    DiscrepancySeverity,
    DiscrepancyType,
    MedicationDiscrepancyResponse,
)
from app.services.analysis_service import InvalidClinicalDocumentIdsError
from app.services.medication_reconciliation_service import (
    SEVERITY_BY_DISCREPANCY_TYPE,
    build_discrepancy_findings,
    run_medication_reconciliation,
)


def _create_user(db, email="reconciliation.user@example.com"):
    user = User(
        email=email,
        hashed_password=hash_password("correcthorse123"),
        name="Reconciliation User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def _create_clinical_document(db, user, document_type="visit_note", title="Visit Note"):
    document = ClinicalDocument(
        user_id=user.id,
        document_type=document_type,
        title=title,
        raw_text="Patient takes Lisinopril 10 mg oral once daily.",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _create_medication(db, user, **overrides):
    payload = {
        "medication_name": "Lisinopril",
        "dose": "10 mg",
        "route": "oral",
        "frequency": "once daily",
        "status": "active",
        "source": "patient_reported",
    }
    payload.update(overrides)

    medication = Medication(user_id=user.id, **payload)
    db.add(medication)
    db.commit()
    db.refresh(medication)

    return medication


def _create_mention(db, document, **overrides):
    payload = {
        "medication_name": "Lisinopril",
        "dose": "10 mg",
        "route": "oral",
        "frequency": "once daily",
        "status": "active",
    }
    payload.update(overrides)

    mention = MedicationMention(clinical_document_id=document.id, **payload)
    db.add(mention)
    db.commit()
    db.refresh(mention)

    return mention


# --- Pure rule tests (build_discrepancy_findings) ---


def test_missing_from_medication_list_finding(db):
    user = _create_user(db, email="missing@example.com")
    document = _create_clinical_document(db, user)
    mention = _create_mention(db, document, medication_name="Atorvastatin")

    findings = build_discrepancy_findings([], [mention], check_unsupported_entries=False)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.discrepancy_type == DiscrepancyType.MISSING_FROM_MEDICATION_LIST
    assert finding.medication_id is None
    assert finding.medication_mention_id == mention.id
    assert finding.severity == DiscrepancySeverity.HIGH
    assert finding.expected_value is None
    assert finding.observed_value == "Atorvastatin"
    assert "Atorvastatin" in finding.title
    assert "Atorvastatin" in finding.ai_explanation


def test_discontinued_status_conflict_finding(db):
    user = _create_user(db, email="discontinued@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(db, user, status="active")
    mention = _create_mention(db, document, status="discontinued")

    findings = build_discrepancy_findings(
        [medication], [mention], check_unsupported_entries=False
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.discrepancy_type == DiscrepancyType.DISCONTINUED_STATUS_CONFLICT
    assert finding.medication_id == medication.id
    assert finding.medication_mention_id == mention.id
    assert finding.severity == DiscrepancySeverity.HIGH
    assert finding.expected_value == "active"
    assert finding.observed_value == "discontinued"


def test_dose_conflict_finding(db):
    user = _create_user(db, email="doseconflict@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(db, user, dose="10 mg")
    mention = _create_mention(db, document, dose="20 mg")

    findings = build_discrepancy_findings(
        [medication], [mention], check_unsupported_entries=False
    )

    assert len(findings) == 1
    finding = findings[0]
    assert finding.discrepancy_type == DiscrepancyType.DOSE_CONFLICT
    assert finding.severity == DiscrepancySeverity.MEDIUM
    assert finding.medication_id == medication.id
    assert finding.medication_mention_id == mention.id
    assert finding.expected_value == "10 mg"
    assert finding.observed_value == "20 mg"


def test_route_conflict_finding(db):
    user = _create_user(db, email="routeconflict@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(db, user, route="oral")
    mention = _create_mention(db, document, route="intravenous")

    findings = build_discrepancy_findings(
        [medication], [mention], check_unsupported_entries=False
    )

    assert len(findings) == 1
    assert findings[0].discrepancy_type == DiscrepancyType.ROUTE_CONFLICT
    assert findings[0].severity == DiscrepancySeverity.MEDIUM


def test_frequency_conflict_finding(db):
    user = _create_user(db, email="frequencyconflict@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(db, user, frequency="once daily")
    mention = _create_mention(db, document, frequency="twice daily")

    findings = build_discrepancy_findings(
        [medication], [mention], check_unsupported_entries=False
    )

    assert len(findings) == 1
    assert findings[0].discrepancy_type == DiscrepancyType.FREQUENCY_CONFLICT
    assert findings[0].severity == DiscrepancySeverity.MEDIUM


def test_general_status_conflict_finding(db):
    user = _create_user(db, email="statusconflict@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(db, user, status="discontinued")
    mention = _create_mention(db, document, status="active")

    findings = build_discrepancy_findings(
        [medication], [mention], check_unsupported_entries=False
    )

    assert len(findings) == 1
    assert findings[0].discrepancy_type == DiscrepancyType.STATUS_CONFLICT
    assert findings[0].severity == DiscrepancySeverity.MEDIUM


def test_general_status_conflict_for_non_discontinued_mismatch(db):
    user = _create_user(db, email="statusstarted@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(db, user, status="active")
    mention = _create_mention(db, document, status="started")

    findings = build_discrepancy_findings(
        [medication], [mention], check_unsupported_entries=False
    )

    assert len(findings) == 1
    assert findings[0].discrepancy_type == DiscrepancyType.STATUS_CONFLICT


def test_unsupported_medication_list_entry_finding_when_eligible(db):
    user = _create_user(db, email="unsupported@example.com")
    medication = _create_medication(db, user, medication_name="Metformin")

    findings = build_discrepancy_findings([medication], [], check_unsupported_entries=True)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.discrepancy_type == DiscrepancyType.UNSUPPORTED_MEDICATION_LIST_ENTRY
    assert finding.medication_id == medication.id
    assert finding.medication_mention_id is None
    assert finding.severity == DiscrepancySeverity.LOW
    assert finding.expected_value == "Metformin"
    assert finding.observed_value is None


def test_no_unsupported_medication_list_entry_finding_when_not_eligible(db):
    user = _create_user(db, email="notchecked@example.com")
    medication = _create_medication(db, user, medication_name="Metformin")

    findings = build_discrepancy_findings([medication], [], check_unsupported_entries=False)

    assert findings == []


def test_no_conflict_when_mention_lacks_comparable_field(db):
    user = _create_user(db, email="missingfield@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(db, user, dose="10 mg")
    mention = _create_mention(db, document, dose=None)

    findings = build_discrepancy_findings(
        [medication], [mention], check_unsupported_entries=False
    )

    assert findings == []


def test_no_findings_for_equivalent_values_after_normalization(db):
    user = _create_user(db, email="equivalent@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(
        db,
        user,
        medication_name="Lisinopril",
        dose="10 MG",
        route="PO",
        frequency="QD",
        status="Active",
    )
    mention = _create_mention(
        db,
        document,
        medication_name="  lisinopril  ",
        dose="10 mg",
        route="oral",
        frequency="daily",
        status="active",
    )

    findings = build_discrepancy_findings(
        [medication], [mention], check_unsupported_entries=False
    )

    assert findings == []


def test_duplicate_identical_mentions_produce_one_finding(db):
    user = _create_user(db, email="duplicate@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(db, user, dose="10 mg")
    mention_a = _create_mention(db, document, dose="20 mg")
    mention_b = _create_mention(db, document, dose="20 mg")

    findings = build_discrepancy_findings(
        [medication], [mention_a, mention_b], check_unsupported_entries=False
    )

    assert len(findings) == 1
    assert findings[0].medication_mention_id == min(mention_a.id, mention_b.id)


def test_multiple_distinct_dose_values_create_separate_findings(db):
    user = _create_user(db, email="multipledistinct@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(db, user, dose="10 mg")
    mention_a = _create_mention(db, document, dose="20 mg")
    mention_b = _create_mention(db, document, dose="30 mg")

    findings = build_discrepancy_findings(
        [medication], [mention_a, mention_b], check_unsupported_entries=False
    )

    assert len(findings) == 2
    assert {finding.observed_value for finding in findings} == {"20 mg", "30 mg"}


def test_one_matching_mention_and_one_contradictory_mention(db):
    user = _create_user(db, email="onematching@example.com")
    document = _create_clinical_document(db, user)
    medication = _create_medication(db, user, dose="10 mg")
    matching_mention = _create_mention(db, document, dose="10 mg")
    conflicting_mention = _create_mention(db, document, dose="20 mg")

    findings = build_discrepancy_findings(
        [medication],
        [matching_mention, conflicting_mention],
        check_unsupported_entries=False,
    )

    assert len(findings) == 1
    assert findings[0].medication_mention_id == conflicting_mention.id
    assert findings[0].observed_value == "20 mg"


def test_findings_link_to_correct_medication_and_mention(db):
    user = _create_user(db, email="correctlinks@example.com")
    document = _create_clinical_document(db, user)
    medication_a = _create_medication(db, user, medication_name="Lisinopril", dose="10 mg")
    medication_b = _create_medication(db, user, medication_name="Metformin", dose="500 mg")
    mention_a = _create_mention(db, document, medication_name="Lisinopril", dose="20 mg")
    mention_b = _create_mention(db, document, medication_name="Metformin", dose="750 mg")

    findings = build_discrepancy_findings(
        [medication_a, medication_b],
        [mention_a, mention_b],
        check_unsupported_entries=False,
    )

    assert len(findings) == 2
    by_medication_id = {finding.medication_id: finding for finding in findings}
    assert by_medication_id[medication_a.id].medication_mention_id == mention_a.id
    assert by_medication_id[medication_b.id].medication_mention_id == mention_b.id


def test_severity_mapping_is_centralized_and_conservative():
    assert (
        SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.MISSING_FROM_MEDICATION_LIST]
        == DiscrepancySeverity.HIGH
    )
    assert (
        SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.DISCONTINUED_STATUS_CONFLICT]
        == DiscrepancySeverity.HIGH
    )
    assert SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.DOSE_CONFLICT] == DiscrepancySeverity.MEDIUM
    assert SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.ROUTE_CONFLICT] == DiscrepancySeverity.MEDIUM
    assert (
        SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.FREQUENCY_CONFLICT]
        == DiscrepancySeverity.MEDIUM
    )
    assert SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.STATUS_CONFLICT] == DiscrepancySeverity.MEDIUM
    assert (
        SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.UNSUPPORTED_MEDICATION_LIST_ENTRY]
        == DiscrepancySeverity.LOW
    )


# --- Orchestration tests (run_medication_reconciliation) ---


def test_run_medication_reconciliation_completes_with_correct_counts(db):
    user = _create_user(db, email="counts@example.com")
    document = _create_clinical_document(db, user)
    _create_medication(db, user, dose="10 mg")
    _create_mention(db, document, dose="20 mg")

    analysis = run_medication_reconciliation(db, user.id, [document.id])

    assert analysis.status == "completed"
    assert analysis.total_findings == 1
    assert analysis.medium_severity_findings == 1
    assert analysis.high_severity_findings == 0
    assert analysis.low_severity_findings == 0


def test_run_medication_reconciliation_sets_timestamps(db):
    user = _create_user(db, email="timestamps@example.com")
    document = _create_clinical_document(db, user)
    _create_medication(db, user)

    analysis = run_medication_reconciliation(db, user.id, [document.id])

    assert analysis.started_at is not None
    assert analysis.completed_at is not None
    assert analysis.completed_at >= analysis.started_at


def test_run_medication_reconciliation_preserves_provider_and_model(db):
    user = _create_user(db, email="providermodel@example.com")
    document = _create_clinical_document(db, user)
    _create_medication(db, user)

    analysis = run_medication_reconciliation(
        db, user.id, [document.id], provider="google", model_name="gemini-pro"
    )

    assert analysis.provider == "google"
    assert analysis.model_name == "gemini-pro"


def test_run_medication_reconciliation_rejects_nonexistent_document(db):
    user = _create_user(db, email="nonexistentdoc@example.com")

    with pytest.raises(InvalidClinicalDocumentIdsError):
        run_medication_reconciliation(db, user.id, [999999])

    assert db.query(Analysis).filter(Analysis.user_id == user.id).count() == 0


def test_run_medication_reconciliation_rejects_document_owned_by_another_user(db):
    user = _create_user(db, email="reconowner@example.com")
    other_user = _create_user(db, email="reconintruder@example.com")
    other_document = _create_clinical_document(db, other_user)

    with pytest.raises(InvalidClinicalDocumentIdsError):
        run_medication_reconciliation(db, user.id, [other_document.id])

    assert db.query(Analysis).filter(Analysis.user_id == user.id).count() == 0


def test_run_medication_reconciliation_succeeds_with_document_with_no_mentions(db):
    user = _create_user(db, email="nomentions@example.com")
    document = _create_clinical_document(db, user)
    _create_medication(db, user)

    analysis = run_medication_reconciliation(db, user.id, [document.id])

    assert analysis.status == "completed"
    assert analysis.total_findings == 0


def test_run_medication_reconciliation_marks_failed_on_unexpected_error(db, monkeypatch):
    user = _create_user(db, email="failure@example.com")
    document = _create_clinical_document(db, user)
    _create_medication(db, user)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure with sensitive detail: password=hunter2")

    monkeypatch.setattr(
        "app.services.medication_reconciliation_service.build_discrepancy_findings", _boom
    )

    analysis = run_medication_reconciliation(db, user.id, [document.id])

    assert analysis.status == "failed"
    assert analysis.error_message == "Reconciliation failed due to an internal error (RuntimeError)."
    assert "hunter2" not in analysis.error_message
    assert analysis.total_findings == 0
    assert analysis.high_severity_findings == 0
    assert analysis.medium_severity_findings == 0
    assert analysis.low_severity_findings == 0
    assert (
        db.query(MedicationDiscrepancy)
        .filter(MedicationDiscrepancy.analysis_id == analysis.id)
        .count()
        == 0
    )


def test_run_medication_reconciliation_rolls_back_staged_discrepancies_on_late_failure(
    db, monkeypatch
):
    user = _create_user(db, email="latefailure@example.com")
    document = _create_clinical_document(db, user)
    _create_medication(db, user, dose="10 mg")
    _create_mention(db, document, dose="20 mg")

    def _boom(*args, **kwargs):
        raise RuntimeError("late failure")

    monkeypatch.setattr(
        "app.services.medication_reconciliation_service.mark_analysis_completed", _boom
    )

    analysis = run_medication_reconciliation(db, user.id, [document.id])

    assert analysis.status == "failed"
    assert (
        db.query(MedicationDiscrepancy)
        .filter(MedicationDiscrepancy.analysis_id == analysis.id)
        .count()
        == 0
    )


def test_run_medication_reconciliation_does_not_use_other_users_medications(db):
    user_a = _create_user(db, email="crossusera@example.com")
    user_b = _create_user(db, email="crossuserb@example.com")

    document_a = _create_clinical_document(db, user_a)
    _create_medication(db, user_b, medication_name="Lisinopril", dose="10 mg")
    _create_mention(db, document_a, medication_name="Lisinopril", dose="20 mg")

    analysis = run_medication_reconciliation(db, user_a.id, [document_a.id])

    assert analysis.status == "completed"
    assert analysis.total_findings == 1

    finding = analysis.medication_discrepancies[0]
    assert finding.discrepancy_type == "missing_from_medication_list"
    assert finding.medication_id is None


def test_completed_analysis_and_discrepancy_serialize_through_response_schemas(db):
    user = _create_user(db, email="serialize@example.com")
    document = _create_clinical_document(db, user)
    _create_medication(db, user, dose="10 mg")
    _create_mention(db, document, dose="20 mg")

    analysis = run_medication_reconciliation(db, user.id, [document.id])

    analysis_response = AnalysisResponse.model_validate(analysis)
    assert analysis_response.status == AnalysisStatus.COMPLETED
    assert analysis_response.total_findings == 1

    discrepancy = analysis.medication_discrepancies[0]
    discrepancy_response = MedicationDiscrepancyResponse.model_validate(discrepancy)
    assert discrepancy_response.discrepancy_type == DiscrepancyType.DOSE_CONFLICT
    assert discrepancy_response.severity == DiscrepancySeverity.MEDIUM
