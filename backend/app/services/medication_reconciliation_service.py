from sqlalchemy.orm import Session

from app.ai.schemas import Medication as AIExtractedMedication
from app.models.analysis import Analysis
from app.models.clinical_document import ClinicalDocument
from app.models.medication import Medication
from app.models.medication_mention import MedicationMention
from app.models.patient import Patient
from app.schemas.analysis import AnalysisCompletedSummary, AnalysisCreate
from app.schemas.medication_discrepancy import (
    DiscrepancySeverity,
    DiscrepancyType,
    MedicationDiscrepancyCreate,
)
from app.services.analysis_service import (
    create_analysis,
    mark_analysis_completed,
    mark_analysis_failed,
    mark_analysis_processing,
    ordered_clinical_documents,
)
from app.services.medication_discrepancy_service import create_medication_discrepancies
from app.services.medication_normalization import (
    normalize_dose,
    normalize_frequency,
    normalize_medication_name,
    normalize_route,
    normalize_status,
)

# Document types that are, by their own documented nature, meant to be a
# comprehensive listing of a patient's current medications. A visit note,
# progress note, or discharge summary is not expected to re-list every
# medication a patient takes, so its silence about a medication proves
# nothing. Only these document types are treated as evidence that an
# unmentioned medication list entry is actually unsupported.
UNSUPPORTED_ENTRY_ELIGIBLE_DOCUMENT_TYPES = {
    "medication_list",
    "medication_reconciliation_form",
}

# Centralized severity mapping. High is reserved for the two conflict types
# with the clearest safety implication: a medication documented as being
# taken that is entirely absent from the user's own list, and an explicit
# active-versus-discontinued contradiction. Medium covers concrete field
# mismatches on an otherwise-matched medication. Low is reserved for the
# weakest-evidence inference, an absence of any mention across a limited,
# possibly incomplete set of selected documents.
SEVERITY_BY_DISCREPANCY_TYPE = {
    DiscrepancyType.MISSING_FROM_MEDICATION_LIST: DiscrepancySeverity.HIGH,
    DiscrepancyType.DISCONTINUED_STATUS_CONFLICT: DiscrepancySeverity.HIGH,
    DiscrepancyType.DOSE_CONFLICT: DiscrepancySeverity.MEDIUM,
    DiscrepancyType.ROUTE_CONFLICT: DiscrepancySeverity.MEDIUM,
    DiscrepancyType.FREQUENCY_CONFLICT: DiscrepancySeverity.MEDIUM,
    DiscrepancyType.STATUS_CONFLICT: DiscrepancySeverity.MEDIUM,
    DiscrepancyType.UNSUPPORTED_MEDICATION_LIST_ENTRY: DiscrepancySeverity.LOW,
}

_FIELD_LABELS = {
    "dose": "dose",
    "route": "route",
    "frequency": "frequency",
}


def _group_by_normalized_name(items, name_getter):
    groups: dict[str, list] = {}

    for item in items:
        normalized = normalize_medication_name(name_getter(item))

        if normalized is None:
            continue

        groups.setdefault(normalized, []).append(item)

    return groups


def _find_missing_from_medication_list(medications_by_name, mentions_by_name):
    findings = []

    for normalized_name, mentions in mentions_by_name.items():
        if normalized_name in medications_by_name:
            continue

        representative = min(mentions, key=lambda mention: mention.id)

        findings.append(
            MedicationDiscrepancyCreate(
                medication_id=None,
                medication_mention_id=representative.id,
                discrepancy_type=DiscrepancyType.MISSING_FROM_MEDICATION_LIST,
                severity=SEVERITY_BY_DISCREPANCY_TYPE[DiscrepancyType.MISSING_FROM_MEDICATION_LIST],
                title=f"{representative.medication_name} not found in medication list",
                ai_explanation=(
                    f"{representative.medication_name} is mentioned in the selected clinical "
                    "documents but does not appear in the current medication list."
                ),
                expected_value=None,
                observed_value=representative.medication_name,
            )
        )

    return findings


def _find_unsupported_medication_list_entries(medications_by_name, mentions_by_name):
    findings = []

    for normalized_name, medications in medications_by_name.items():
        if normalized_name in mentions_by_name:
            continue

        canonical = min(medications, key=lambda medication: medication.id)

        findings.append(
            MedicationDiscrepancyCreate(
                medication_id=canonical.id,
                medication_mention_id=None,
                discrepancy_type=DiscrepancyType.UNSUPPORTED_MEDICATION_LIST_ENTRY,
                severity=SEVERITY_BY_DISCREPANCY_TYPE[
                    DiscrepancyType.UNSUPPORTED_MEDICATION_LIST_ENTRY
                ],
                title=f"{canonical.medication_name} not mentioned in selected documents",
                ai_explanation=(
                    f"{canonical.medication_name} is in the current medication list but does not "
                    "appear in any selected medication list or medication reconciliation document."
                ),
                expected_value=canonical.medication_name,
                observed_value=None,
            )
        )

    return findings


def _find_field_conflicts(
    medication: Medication,
    mentions: list[MedicationMention],
    field_name: str,
    normalize_fn,
    discrepancy_type: DiscrepancyType,
) -> list[MedicationDiscrepancyCreate]:
    medication_value = getattr(medication, field_name)
    normalized_medication_value = normalize_fn(medication_value)

    if normalized_medication_value is None:
        return []

    groups: dict[str, list[MedicationMention]] = {}

    for mention in mentions:
        mention_value = getattr(mention, field_name)
        normalized_mention_value = normalize_fn(mention_value)

        if normalized_mention_value is None:
            continue

        if normalized_mention_value == normalized_medication_value:
            continue

        groups.setdefault(normalized_mention_value, []).append(mention)

    findings = []
    label = _FIELD_LABELS[field_name]

    for group_mentions in groups.values():
        representative = min(group_mentions, key=lambda mention: mention.id)
        observed_value = getattr(representative, field_name)

        findings.append(
            MedicationDiscrepancyCreate(
                medication_id=medication.id,
                medication_mention_id=representative.id,
                discrepancy_type=discrepancy_type,
                severity=SEVERITY_BY_DISCREPANCY_TYPE[discrepancy_type],
                title=f"{medication.medication_name} {label} does not match",
                ai_explanation=(
                    f"The medication list records a {label} of {medication_value} for "
                    f"{medication.medication_name}, but a selected document records "
                    f"{observed_value}."
                ),
                expected_value=medication_value,
                observed_value=observed_value,
            )
        )

    return findings


def _find_status_conflicts(
    medication: Medication, mentions: list[MedicationMention]
) -> list[MedicationDiscrepancyCreate]:
    normalized_medication_status = normalize_status(medication.status)

    if normalized_medication_status is None:
        return []

    groups: dict[str, list[MedicationMention]] = {}

    for mention in mentions:
        normalized_mention_status = normalize_status(mention.status)

        if normalized_mention_status is None:
            continue

        if normalized_mention_status == normalized_medication_status:
            continue

        groups.setdefault(normalized_mention_status, []).append(mention)

    findings = []

    for normalized_value, group_mentions in groups.items():
        representative = min(group_mentions, key=lambda mention: mention.id)

        if normalized_medication_status == "active" and normalized_value == "discontinued":
            discrepancy_type = DiscrepancyType.DISCONTINUED_STATUS_CONFLICT
            title = f"{medication.medication_name} marked discontinued in a document"
            explanation = (
                f"{medication.medication_name} is active in the medication list but a selected "
                "document states it was discontinued."
            )
        else:
            discrepancy_type = DiscrepancyType.STATUS_CONFLICT
            title = f"{medication.medication_name} status does not match"
            explanation = (
                f"The medication list records a status of {medication.status} for "
                f"{medication.medication_name}, but a selected document records "
                f"{representative.status}."
            )

        findings.append(
            MedicationDiscrepancyCreate(
                medication_id=medication.id,
                medication_mention_id=representative.id,
                discrepancy_type=discrepancy_type,
                severity=SEVERITY_BY_DISCREPANCY_TYPE[discrepancy_type],
                title=title,
                ai_explanation=explanation,
                expected_value=medication.status,
                observed_value=representative.status,
            )
        )

    return findings


def build_discrepancy_findings(
    medications: list[Medication],
    mentions: list[MedicationMention],
    check_unsupported_entries: bool,
) -> list[MedicationDiscrepancyCreate]:
    medications_by_name = _group_by_normalized_name(
        medications, lambda medication: medication.medication_name
    )
    mentions_by_name = _group_by_normalized_name(mentions, lambda mention: mention.medication_name)

    findings: list[MedicationDiscrepancyCreate] = []

    findings.extend(_find_missing_from_medication_list(medications_by_name, mentions_by_name))

    for normalized_name, name_mentions in mentions_by_name.items():
        if normalized_name not in medications_by_name:
            continue

        canonical_medication = min(
            medications_by_name[normalized_name], key=lambda medication: medication.id
        )

        findings.extend(_find_status_conflicts(canonical_medication, name_mentions))
        findings.extend(
            _find_field_conflicts(
                canonical_medication,
                name_mentions,
                "dose",
                normalize_dose,
                DiscrepancyType.DOSE_CONFLICT,
            )
        )
        findings.extend(
            _find_field_conflicts(
                canonical_medication,
                name_mentions,
                "route",
                normalize_route,
                DiscrepancyType.ROUTE_CONFLICT,
            )
        )
        findings.extend(
            _find_field_conflicts(
                canonical_medication,
                name_mentions,
                "frequency",
                normalize_frequency,
                DiscrepancyType.FREQUENCY_CONFLICT,
            )
        )

    if check_unsupported_entries:
        findings.extend(
            _find_unsupported_medication_list_entries(medications_by_name, mentions_by_name)
        )

    return findings


def count_findings_by_severity(findings: list[MedicationDiscrepancyCreate]) -> dict[str, int]:
    counts = {"total": len(findings), "high": 0, "medium": 0, "low": 0}

    for finding in findings:
        counts[finding.severity.value] += 1

    return counts


def _build_summary_text(counts: dict[str, int], document_count: int) -> str:
    return (
        f"Reconciliation completed across {document_count} clinical document(s) with "
        f"{counts['total']} finding(s): {counts['high']} high, {counts['medium']} medium, "
        f"{counts['low']} low severity."
    )


def _safe_error_message(error: Exception) -> str:
    return f"Reconciliation failed due to an internal error ({type(error).__name__})."


def reconcile_medications(
    db: Session,
    analysis: Analysis,
    medications: list[Medication],
    mentions: list[MedicationMention],
    check_unsupported_entries: bool,
) -> dict[str, int]:
    """Builds discrepancy findings and persists them against the given
    analysis, returning severity counts.

    Does not create, commit, or complete the analysis itself; callers own
    that lifecycle (see run_medication_reconciliation below, and Issue
    #148's reconcile_ai_extracted_medications, which both call this).
    create_medication_discrepancies does not commit, so this function's
    writes only take effect once the caller's own commit runs (Analysis
    completion, or a rollback on failure); see docs/architecture.md.
    """
    findings = build_discrepancy_findings(medications, mentions, check_unsupported_entries)

    create_medication_discrepancies(db, analysis.id, findings)

    return count_findings_by_severity(findings)


def _resolve_source_document_id(
    source_note: int | None,
    ordered_documents: list[ClinicalDocument],
    fallback_document_id: int,
) -> int:
    """Maps an AI-reported "source_note" (1-indexed, matching the "Note N"
    labels app/ai/prompts.py's build_summary_prompt assigns) back to the
    real document at that position in `ordered_documents`, the exact same
    order that was used to build the prompt in the first place (see
    ordered_clinical_documents, analysis_service.py).

    Falls back to `fallback_document_id` (the lowest-id selected document,
    the same placeholder Issue #148 always used) only when the AI omitted
    source_note entirely, or reported a number outside the actual range of
    selected documents, both malformed-response cases that the prompt
    instructs against but that `Medication.source_note` deliberately allows
    (it's optional, not required; see app/ai/schemas.py) rather than
    failing the whole analysis over one mis-attributed medication.
    """
    if source_note is None:
        return fallback_document_id

    index = source_note - 1
    if index < 0 or index >= len(ordered_documents):
        return fallback_document_id

    return ordered_documents[index].id


def reconcile_ai_extracted_medications(
    db: Session,
    analysis: Analysis,
    ai_medications: list[AIExtractedMedication],
) -> dict[str, int]:
    """Bridges the AI clinical-summary flow (Issue #41/#130) into
    reconciliation (Issue #148).

    That flow extracts medications directly from clinical note text via an
    AI provider, without ever persisting a MedicationMention row; it only
    ever produced AnalysisMedicationMention rows, an AI-authored observation
    with no link back to a specific document (see
    app/services/analysis_result_service.py), so there was nothing here
    for reconciliation to compare against. This function closes that gap by
    persisting each AI-extracted medication as a real MedicationMention, so
    the exact same reconciliation engine used by run_medication_reconciliation
    (below) can run against it.

    Document-level provenance (Issue #152): the AI's prompt numbers each
    selected document ("Note 1", "Note 2", ... see app/ai/prompts.py) and,
    as of this issue, its response reports which numbered note each
    medication actually came from (`Medication.source_note`). Each mention
    is attached to that real document via _resolve_source_document_id,
    falling back to the lowest-id selected document only for the rare
    malformed response that omits or misreports the note number, not, as
    before, unconditionally for every mention regardless of source. A
    medication mentioned in more than one selected document is expected to
    appear as more than one entry in `ai_medications` (one per note it was
    found in, per the prompt's own instructions) and so becomes more than
    one MedicationMention, one correctly attached to each real source
    document; build_discrepancy_findings already groups mentions of the
    same medication name together regardless of how many there are or which
    document each came from, so this needed no change there.

    Historical analyses created before this issue still have their
    MedicationMention rows attached to whichever document happened to have
    the lowest id among those selected, not necessarily their true source;
    this function cannot retroactively correct data it didn't write, and no
    migration re-derives it (the original note text isn't stored per
    mention, so which document a historical mention "really" came from
    can't be recovered after the fact). Only analyses created from this
    point forward get true provenance.

    Medications and MedicationMentions are queried/created the same way
    run_medication_reconciliation does, so the exact same discrepancy rules
    apply either way.
    """
    if not ai_medications:
        return {"total": 0, "high": 0, "medium": 0, "low": 0}

    documents = ordered_clinical_documents(analysis)
    fallback_document_id = documents[0].id

    mentions: list[MedicationMention] = []

    for ai_medication in ai_medications:
        source_document_id = _resolve_source_document_id(
            ai_medication.source_note, documents, fallback_document_id
        )
        mention = MedicationMention(
            clinical_document_id=source_document_id,
            medication_name=ai_medication.name,
            dose=ai_medication.dosage,
            route=ai_medication.route,
            frequency=ai_medication.frequency,
            status=ai_medication.status,
            context_text=ai_medication.notes,
        )
        db.add(mention)
        mentions.append(mention)

    # Assigns ids to the mentions above without committing, so
    # MedicationDiscrepancyCreate.medication_mention_id can reference them -
    # the transaction as a whole is still only committed by the caller.
    db.flush()

    medications = db.query(Medication).filter(Medication.patient_id == analysis.patient_id).all()

    check_unsupported_entries = any(
        document.document_type in UNSUPPORTED_ENTRY_ELIGIBLE_DOCUMENT_TYPES
        for document in documents
    )

    return reconcile_medications(db, analysis, medications, mentions, check_unsupported_entries)


def run_medication_reconciliation(
    db: Session,
    patient: Patient,
    clinical_document_ids: list[int],
    provider: str | None = None,
    model_name: str | None = None,
) -> Analysis:
    analysis = create_analysis(
        db, patient, AnalysisCreate(clinical_document_ids=clinical_document_ids)
    )

    try:
        mark_analysis_processing(db, analysis)

        documents = analysis.clinical_documents
        document_ids = [document.id for document in documents]

        # Scoped to this patient specifically, not the wider set of every
        # medication the provider (User) has ever entered across all of
        # their patients. This is the one place reconciliation reads
        # Medication directly rather than through medication_service, so
        # it needed its own explicit patient_id fix (Sprint 3.5, Issue #130)
        # once Medication moved to patient ownership.
        medications = db.query(Medication).filter(Medication.patient_id == patient.id).all()
        mentions = (
            db.query(MedicationMention)
            .filter(MedicationMention.clinical_document_id.in_(document_ids))
            .all()
        )

        check_unsupported_entries = any(
            document.document_type in UNSUPPORTED_ENTRY_ELIGIBLE_DOCUMENT_TYPES
            for document in documents
        )

        counts = reconcile_medications(
            db, analysis, medications, mentions, check_unsupported_entries
        )

        summary_in = AnalysisCompletedSummary(
            summary=_build_summary_text(counts, len(documents)),
            total_findings=counts["total"],
            high_severity_findings=counts["high"],
            medium_severity_findings=counts["medium"],
            low_severity_findings=counts["low"],
            provider=provider,
            model_name=model_name,
        )

        mark_analysis_completed(db, analysis, summary_in)

        return analysis

    except Exception as error:
        db.rollback()
        mark_analysis_failed(db, analysis, _safe_error_message(error))

        return analysis
