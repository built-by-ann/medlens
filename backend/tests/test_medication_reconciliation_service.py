from datetime import date

import pytest

from app.ai.schemas import Medication as AIExtractedMedication
from app.core.security import hash_password
from app.models.analysis import Analysis
from app.models.clinical_document import ClinicalDocument
from app.models.medication import Medication
from app.models.medication_discrepancy import MedicationDiscrepancy
from app.models.medication_mention import MedicationMention
from app.models.patient import Patient
from app.models.user import User
from app.schemas.analysis import AnalysisCreate, AnalysisDetailResponse, AnalysisStatus
from app.schemas.medication_discrepancy import (
    DiscrepancySeverity,
    DiscrepancyType,
    MedicationDiscrepancyResponse,
)
from app.services.analysis_service import InvalidClinicalDocumentIdsError, create_analysis
from app.services.medication_reconciliation_service import (
    SEVERITY_BY_DISCREPANCY_TYPE,
    build_discrepancy_findings,
    reconcile_ai_extracted_medications,
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


def _create_clinical_document(db, patient, document_type="visit_note", title="Visit Note"):
    document = ClinicalDocument(
        patient_id=patient.id,
        document_type=document_type,
        title=title,
        raw_text="Patient takes Lisinopril 10 mg oral once daily.",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _create_medication(db, patient, **overrides):
    payload = {
        "medication_name": "Lisinopril",
        "dose": "10 mg",
        "route": "oral",
        "frequency": "once daily",
        "status": "active",
        "source": "patient_reported",
    }
    payload.update(overrides)

    medication = Medication(patient_id=patient.id, **payload)
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
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
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
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, status="active")
    mention = _create_mention(db, document, status="discontinued")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

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
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, dose="10 mg")
    mention = _create_mention(db, document, dose="20 mg")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

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
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, route="oral")
    mention = _create_mention(db, document, route="intravenous")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert len(findings) == 1
    assert findings[0].discrepancy_type == DiscrepancyType.ROUTE_CONFLICT
    assert findings[0].severity == DiscrepancySeverity.MEDIUM


def test_frequency_conflict_finding(db):
    user = _create_user(db, email="frequencyconflict@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, frequency="once daily")
    mention = _create_mention(db, document, frequency="twice daily")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert len(findings) == 1
    assert findings[0].discrepancy_type == DiscrepancyType.FREQUENCY_CONFLICT
    assert findings[0].severity == DiscrepancySeverity.MEDIUM


def test_general_status_conflict_finding(db):
    user = _create_user(db, email="statusconflict@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, status="discontinued")
    mention = _create_mention(db, document, status="active")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert len(findings) == 1
    assert findings[0].discrepancy_type == DiscrepancyType.STATUS_CONFLICT
    assert findings[0].severity == DiscrepancySeverity.MEDIUM


def test_general_status_conflict_for_non_discontinued_mismatch(db):
    user = _create_user(db, email="statusstarted@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, status="active")
    mention = _create_mention(db, document, status="started")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert len(findings) == 1
    assert findings[0].discrepancy_type == DiscrepancyType.STATUS_CONFLICT


def test_unsupported_medication_list_entry_finding_when_eligible(db):
    user = _create_user(db, email="unsupported@example.com")
    patient = _create_patient(db, user)
    medication = _create_medication(db, patient, medication_name="Metformin")

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
    patient = _create_patient(db, user)
    medication = _create_medication(db, patient, medication_name="Metformin")

    findings = build_discrepancy_findings([medication], [], check_unsupported_entries=False)

    assert findings == []


def test_no_conflict_when_mention_lacks_comparable_field(db):
    user = _create_user(db, email="missingfield@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, dose="10 mg")
    mention = _create_mention(db, document, dose=None)

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert findings == []


def test_no_findings_for_equivalent_values_after_normalization(db):
    user = _create_user(db, email="equivalent@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(
        db,
        patient,
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

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert findings == []


def test_duplicate_identical_mentions_produce_one_finding(db):
    user = _create_user(db, email="duplicate@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, dose="10 mg")
    mention_a = _create_mention(db, document, dose="20 mg")
    mention_b = _create_mention(db, document, dose="20 mg")

    findings = build_discrepancy_findings(
        [medication], [mention_a, mention_b], check_unsupported_entries=False
    )

    assert len(findings) == 1
    assert findings[0].medication_mention_id == min(mention_a.id, mention_b.id)


def test_multiple_distinct_dose_values_create_separate_findings(db):
    user = _create_user(db, email="multipledistinct@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, dose="10 mg")
    mention_a = _create_mention(db, document, dose="20 mg")
    mention_b = _create_mention(db, document, dose="30 mg")

    findings = build_discrepancy_findings(
        [medication], [mention_a, mention_b], check_unsupported_entries=False
    )

    assert len(findings) == 2
    assert {finding.observed_value for finding in findings} == {"20 mg", "30 mg"}


def test_one_matching_mention_and_one_contradictory_mention(db):
    user = _create_user(db, email="onematching@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, dose="10 mg")
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
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication_a = _create_medication(db, patient, medication_name="Lisinopril", dose="10 mg")
    medication_b = _create_medication(db, patient, medication_name="Metformin", dose="500 mg")
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
    assert (
        SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.ROUTE_CONFLICT] == DiscrepancySeverity.MEDIUM
    )
    assert (
        SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.FREQUENCY_CONFLICT]
        == DiscrepancySeverity.MEDIUM
    )
    assert (
        SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.STATUS_CONFLICT] == DiscrepancySeverity.MEDIUM
    )
    assert (
        SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.UNSUPPORTED_MEDICATION_LIST_ENTRY]
        == DiscrepancySeverity.LOW
    )


def test_no_discrepancies_when_names_and_fields_match_exactly(db):
    user = _create_user(db, email="exactmatch@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient)
    mention = _create_mention(db, document)

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=True)

    assert findings == []


def test_case_insensitive_name_matching_links_to_same_medication(db):
    user = _create_user(db, email="caseinsensitive@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, medication_name="LISINOPRIL", dose="10 mg")
    mention = _create_mention(db, document, medication_name="lisinopril", dose="20 mg")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    # A single dose conflict, rather than a missing-from-list finding plus an
    # unsupported-entry finding, proves the two names were matched as the
    # same medication despite the case difference.
    assert len(findings) == 1
    assert findings[0].discrepancy_type == DiscrepancyType.DOSE_CONFLICT
    assert findings[0].medication_id == medication.id


def test_status_match_active_produces_no_finding(db):
    user = _create_user(db, email="activematch@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, status="active")
    mention = _create_mention(db, document, status="active")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert findings == []


def test_status_match_discontinued_produces_no_finding(db):
    user = _create_user(db, email="discontinuedmatch@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, status="discontinued")
    mention = _create_mention(db, document, status="discontinued")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert findings == []


def test_unrecognized_status_value_matches_itself_without_a_finding(db):
    user = _create_user(db, email="unknownstatusmatch@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, status="on hold")
    mention = _create_mention(db, document, status="on hold")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert findings == []


def test_unrecognized_status_mismatch_produces_general_conflict_not_discontinued(db):
    user = _create_user(db, email="unknownstatusmismatch@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, status="on hold")
    mention = _create_mention(db, document, status="active")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert len(findings) == 1
    assert findings[0].discrepancy_type == DiscrepancyType.STATUS_CONFLICT
    assert findings[0].severity == DiscrepancySeverity.MEDIUM


def test_dose_present_only_on_mention_produces_no_finding(db):
    # dose is nullable=False on Medication, so "the medication has no dose"
    # is represented as an empty string, which normalize_dose reduces to
    # None, exercising the same early-return branch as a genuinely absent
    # value. This is the reverse of test_no_conflict_when_mention_lacks_
    # comparable_field, which covers the mention lacking a value instead.
    user = _create_user(db, email="mentiondoseonly@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    medication = _create_medication(db, patient, dose="")
    mention = _create_mention(db, document, dose="10 mg")

    findings = build_discrepancy_findings([medication], [mention], check_unsupported_entries=False)

    assert findings == []


def test_multiple_discrepancy_types_in_a_single_run(db):
    user = _create_user(db, email="multipletypes@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)

    dose_conflict_medication = _create_medication(
        db, patient, medication_name="Lisinopril", dose="10 mg"
    )
    unsupported_medication = _create_medication(db, patient, medication_name="Metformin")

    dose_conflict_mention = _create_mention(
        db, document, medication_name="Lisinopril", dose="20 mg"
    )
    missing_mention = _create_mention(db, document, medication_name="Atorvastatin")

    findings = build_discrepancy_findings(
        [dose_conflict_medication, unsupported_medication],
        [dose_conflict_mention, missing_mention],
        check_unsupported_entries=True,
    )

    assert len(findings) == 3
    findings_by_type = {finding.discrepancy_type: finding for finding in findings}
    assert set(findings_by_type) == {
        DiscrepancyType.DOSE_CONFLICT,
        DiscrepancyType.UNSUPPORTED_MEDICATION_LIST_ENTRY,
        DiscrepancyType.MISSING_FROM_MEDICATION_LIST,
    }
    assert findings_by_type[DiscrepancyType.DOSE_CONFLICT].severity == DiscrepancySeverity.MEDIUM
    assert (
        findings_by_type[DiscrepancyType.UNSUPPORTED_MEDICATION_LIST_ENTRY].severity
        == DiscrepancySeverity.LOW
    )
    assert (
        findings_by_type[DiscrepancyType.MISSING_FROM_MEDICATION_LIST].severity
        == DiscrepancySeverity.HIGH
    )


# --- Document provenance tests (reconcile_ai_extracted_medications, Issue #152) ---


def _ai_medication(name="Lisinopril", source_note=None, **overrides):
    payload = {"name": name, "source_note": source_note}
    payload.update(overrides)

    return AIExtractedMedication(**payload)


def test_reconcile_ai_extracted_medications_attaches_mention_to_its_actual_source_document(db):
    user = _create_user(db, email="provenancesingle@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    analysis = create_analysis(db, patient, AnalysisCreate(clinical_document_ids=[document.id]))

    reconcile_ai_extracted_medications(db, analysis, [_ai_medication(source_note=1)])

    mention = (
        db.query(MedicationMention).filter(MedicationMention.medication_name == "Lisinopril").one()
    )
    assert mention.clinical_document_id == document.id


def test_reconcile_ai_extracted_medications_attributes_each_medication_to_its_own_document(db):
    # Two distinct medications, each mentioned in a different one of the two
    # selected documents; the true-provenance case Issue #148's placeholder
    # could never represent correctly.
    user = _create_user(db, email="provenancemulti@example.com")
    patient = _create_patient(db, user)
    document_a = _create_clinical_document(db, patient, title="Visit Note")
    document_b = _create_clinical_document(db, patient, title="Discharge Summary")
    analysis = create_analysis(
        db, patient, AnalysisCreate(clinical_document_ids=[document_a.id, document_b.id])
    )

    reconcile_ai_extracted_medications(
        db,
        analysis,
        [
            _ai_medication(name="Lisinopril", source_note=1),
            _ai_medication(name="Metformin", source_note=2),
        ],
    )

    lisinopril = db.query(MedicationMention).filter_by(medication_name="Lisinopril").one()
    metformin = db.query(MedicationMention).filter_by(medication_name="Metformin").one()
    assert lisinopril.clinical_document_id == document_a.id
    assert metformin.clinical_document_id == document_b.id


def test_reconcile_ai_extracted_medications_attributes_repeated_medication_to_each_document(db):
    # The same medication mentioned in both selected documents becomes two
    # MedicationMention rows, each attached to its own real source document -
    # not collapsed onto a single document the way the old placeholder did.
    user = _create_user(db, email="provenancerepeated@example.com")
    patient = _create_patient(db, user)
    document_a = _create_clinical_document(db, patient, title="Visit Note")
    document_b = _create_clinical_document(db, patient, title="Follow-up Note")
    analysis = create_analysis(
        db, patient, AnalysisCreate(clinical_document_ids=[document_a.id, document_b.id])
    )

    reconcile_ai_extracted_medications(
        db,
        analysis,
        [
            _ai_medication(name="Lisinopril", dosage="10 mg", source_note=1),
            _ai_medication(name="Lisinopril", dosage="20 mg", source_note=2),
        ],
    )

    mentions = {
        mention.dose: mention.clinical_document_id
        for mention in db.query(MedicationMention).filter_by(medication_name="Lisinopril").all()
    }
    assert mentions == {"10 mg": document_a.id, "20 mg": document_b.id}


def test_reconcile_ai_extracted_medications_falls_back_to_lowest_id_document_when_source_note_missing(
    db,
):
    user = _create_user(db, email="provenancefallbackmissing@example.com")
    patient = _create_patient(db, user)
    document_a = _create_clinical_document(db, patient, title="Visit Note")
    document_b = _create_clinical_document(db, patient, title="Discharge Summary")
    analysis = create_analysis(
        db, patient, AnalysisCreate(clinical_document_ids=[document_a.id, document_b.id])
    )
    lowest_id_document = min(document_a, document_b, key=lambda document: document.id)

    reconcile_ai_extracted_medications(db, analysis, [_ai_medication(source_note=None)])

    mention = db.query(MedicationMention).filter_by(medication_name="Lisinopril").one()
    assert mention.clinical_document_id == lowest_id_document.id


def test_reconcile_ai_extracted_medications_falls_back_to_lowest_id_document_when_source_note_out_of_range(
    db,
):
    user = _create_user(db, email="provenancefallbackinvalid@example.com")
    patient = _create_patient(db, user)
    document_a = _create_clinical_document(db, patient, title="Visit Note")
    document_b = _create_clinical_document(db, patient, title="Discharge Summary")
    analysis = create_analysis(
        db, patient, AnalysisCreate(clinical_document_ids=[document_a.id, document_b.id])
    )
    lowest_id_document = min(document_a, document_b, key=lambda document: document.id)

    # There are only 2 selected documents; "Note 99" does not exist.
    reconcile_ai_extracted_medications(db, analysis, [_ai_medication(source_note=99)])

    mention = db.query(MedicationMention).filter_by(medication_name="Lisinopril").one()
    assert mention.clinical_document_id == lowest_id_document.id


def test_reconcile_ai_extracted_medications_still_runs_reconciliation_against_correctly_attributed_mentions(
    db,
):
    # Confirms build_discrepancy_findings needed no change: it already
    # groups mentions of the same medication name together regardless of
    # which document each came from.
    user = _create_user(db, email="provenancereconciles@example.com")
    patient = _create_patient(db, user)
    document_a = _create_clinical_document(db, patient, title="Visit Note")
    document_b = _create_clinical_document(db, patient, title="Discharge Summary")
    _create_medication(db, patient, medication_name="Lisinopril", dose="10 mg")
    analysis = create_analysis(
        db, patient, AnalysisCreate(clinical_document_ids=[document_a.id, document_b.id])
    )

    counts = reconcile_ai_extracted_medications(
        db,
        analysis,
        [_ai_medication(name="Lisinopril", dosage="20 mg", source_note=2)],
    )

    assert counts["total"] == 1
    assert counts["medium"] == 1

    # create_medication_discrepancies deliberately doesn't commit (a real
    # caller commits once everything for the analysis is staged; see
    # persist_analysis_result); this test stands in for that caller.
    db.commit()

    discrepancy = db.query(MedicationDiscrepancy).filter_by(analysis_id=analysis.id).one()
    mention = db.get(MedicationMention, discrepancy.medication_mention_id)
    assert mention.clinical_document_id == document_b.id


# --- Orchestration tests (run_medication_reconciliation) ---


def test_run_medication_reconciliation_completes_with_correct_counts(db):
    user = _create_user(db, email="counts@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    _create_medication(db, patient, dose="10 mg")
    _create_mention(db, document, dose="20 mg")

    analysis = run_medication_reconciliation(db, patient, [document.id])

    assert analysis.status == "completed"
    assert analysis.total_findings == 1
    assert analysis.medium_severity_findings == 1
    assert analysis.high_severity_findings == 0
    assert analysis.low_severity_findings == 0


def test_run_medication_reconciliation_sets_timestamps(db):
    user = _create_user(db, email="timestamps@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    _create_medication(db, patient)

    analysis = run_medication_reconciliation(db, patient, [document.id])

    assert analysis.started_at is not None
    assert analysis.completed_at is not None
    assert analysis.completed_at >= analysis.started_at


def test_run_medication_reconciliation_preserves_provider_and_model(db):
    user = _create_user(db, email="providermodel@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    _create_medication(db, patient)

    analysis = run_medication_reconciliation(
        db, patient, [document.id], provider="google", model_name="gemini-pro"
    )

    assert analysis.provider == "google"
    assert analysis.model_name == "gemini-pro"


def test_run_medication_reconciliation_rejects_nonexistent_document(db):
    user = _create_user(db, email="nonexistentdoc@example.com")
    patient = _create_patient(db, user)

    with pytest.raises(InvalidClinicalDocumentIdsError):
        run_medication_reconciliation(db, patient, [999999])

    assert db.query(Analysis).filter(Analysis.patient_id == patient.id).count() == 0


def test_run_medication_reconciliation_rejects_document_owned_by_another_user(db):
    user = _create_user(db, email="reconowner@example.com")
    other_user = _create_user(db, email="reconintruder@example.com")
    patient = _create_patient(db, user)
    other_patient = _create_patient(db, other_user)
    other_document = _create_clinical_document(db, other_patient)

    with pytest.raises(InvalidClinicalDocumentIdsError):
        run_medication_reconciliation(db, patient, [other_document.id])

    assert db.query(Analysis).filter(Analysis.patient_id == patient.id).count() == 0


def test_run_medication_reconciliation_rejects_document_of_a_different_patient_of_the_same_user(
    db,
):
    user = _create_user(db, email="reconcrosspatient@example.com")
    patient_a = _create_patient(db, user, first_name="A")
    patient_b = _create_patient(db, user, first_name="B")
    document_a = _create_clinical_document(db, patient_a)

    with pytest.raises(InvalidClinicalDocumentIdsError):
        run_medication_reconciliation(db, patient_b, [document_a.id])

    assert db.query(Analysis).filter(Analysis.patient_id == patient_b.id).count() == 0


def test_run_medication_reconciliation_succeeds_with_document_with_no_mentions(db):
    user = _create_user(db, email="nomentions@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    _create_medication(db, patient)

    analysis = run_medication_reconciliation(db, patient, [document.id])

    assert analysis.status == "completed"
    assert analysis.total_findings == 0


def test_run_medication_reconciliation_marks_failed_on_unexpected_error(db, monkeypatch):
    user = _create_user(db, email="failure@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    _create_medication(db, patient)

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure with sensitive detail: password=hunter2")

    monkeypatch.setattr(
        "app.services.medication_reconciliation_service.build_discrepancy_findings", _boom
    )

    analysis = run_medication_reconciliation(db, patient, [document.id])

    assert analysis.status == "failed"
    assert (
        analysis.error_message == "Reconciliation failed due to an internal error (RuntimeError)."
    )
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
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    _create_medication(db, patient, dose="10 mg")
    _create_mention(db, document, dose="20 mg")

    def _boom(*args, **kwargs):
        raise RuntimeError("late failure")

    monkeypatch.setattr(
        "app.services.medication_reconciliation_service.mark_analysis_completed", _boom
    )

    analysis = run_medication_reconciliation(db, patient, [document.id])

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
    patient_a = _create_patient(db, user_a)
    patient_b = _create_patient(db, user_b)

    document_a = _create_clinical_document(db, patient_a)
    _create_medication(db, patient_b, medication_name="Lisinopril", dose="10 mg")
    _create_mention(db, document_a, medication_name="Lisinopril", dose="20 mg")

    analysis = run_medication_reconciliation(db, patient_a, [document_a.id])

    assert analysis.status == "completed"
    assert analysis.total_findings == 1

    finding = analysis.medication_discrepancies[0]
    assert finding.discrepancy_type == "missing_from_medication_list"
    assert finding.medication_id is None


def test_run_medication_reconciliation_does_not_use_another_patients_medications_of_the_same_user(
    db,
):
    # Distinct from test_run_medication_reconciliation_does_not_use_other_users_medications:
    # here both patients belong to the SAME user, so this proves the
    # reconciliation medication lookup is scoped by patient_id and not
    # merely by the wider set of every medication that user has ever
    # entered across all of their patients.
    user = _create_user(db, email="crosspatientreconciliation@example.com")
    patient_a = _create_patient(db, user, first_name="A")
    patient_b = _create_patient(db, user, first_name="B")

    document_a = _create_clinical_document(db, patient_a)
    _create_medication(db, patient_b, medication_name="Lisinopril", dose="10 mg")
    _create_mention(db, document_a, medication_name="Lisinopril", dose="20 mg")

    analysis = run_medication_reconciliation(db, patient_a, [document_a.id])

    assert analysis.status == "completed"
    assert analysis.total_findings == 1

    finding = analysis.medication_discrepancies[0]
    assert finding.discrepancy_type == "missing_from_medication_list"
    assert finding.medication_id is None


def test_completed_analysis_and_discrepancy_serialize_through_response_schemas(db):
    user = _create_user(db, email="serialize@example.com")
    patient = _create_patient(db, user)
    document = _create_clinical_document(db, patient)
    _create_medication(db, patient, dose="10 mg")
    _create_mention(db, document, dose="20 mg")

    analysis = run_medication_reconciliation(db, patient, [document.id])

    analysis_response = AnalysisDetailResponse.model_validate(analysis)
    assert analysis_response.status == AnalysisStatus.COMPLETED
    assert analysis.total_findings == 1

    discrepancy = analysis.medication_discrepancies[0]
    discrepancy_response = MedicationDiscrepancyResponse.model_validate(discrepancy)
    assert discrepancy_response.discrepancy_type == DiscrepancyType.DOSE_CONFLICT
    assert discrepancy_response.severity == DiscrepancySeverity.MEDIUM
