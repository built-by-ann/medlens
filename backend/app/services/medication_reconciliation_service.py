from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.models.medication import Medication
from app.models.medication_mention import MedicationMention
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
                severity=SEVERITY_BY_DISCREPANCY_TYPE[
                    DiscrepancyType.MISSING_FROM_MEDICATION_LIST
                ],
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


def _count_by_severity(findings: list[MedicationDiscrepancyCreate]) -> dict[str, int]:
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


def run_medication_reconciliation(
    db: Session,
    user_id: int,
    clinical_document_ids: list[int],
    provider: str | None = None,
    model_name: str | None = None,
) -> Analysis:
    analysis = create_analysis(
        db, user_id, AnalysisCreate(clinical_document_ids=clinical_document_ids)
    )

    try:
        mark_analysis_processing(db, analysis)

        documents = analysis.clinical_documents
        document_ids = [document.id for document in documents]

        medications = db.query(Medication).filter(Medication.user_id == user_id).all()
        mentions = (
            db.query(MedicationMention)
            .filter(MedicationMention.clinical_document_id.in_(document_ids))
            .all()
        )

        check_unsupported_entries = any(
            document.document_type in UNSUPPORTED_ENTRY_ELIGIBLE_DOCUMENT_TYPES
            for document in documents
        )

        findings = build_discrepancy_findings(medications, mentions, check_unsupported_entries)

        create_medication_discrepancies(db, analysis.id, findings)

        counts = _count_by_severity(findings)

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
