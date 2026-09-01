"""Medication matching for the evaluation metrics scorer (Issue #90).

Pairs predicted medications with expected (ground-truth) medications
within one benchmark case, establishing which extracted medications are
correct (TP), spurious (FP), or missed (FN) - before any attribute
(dosage/route/frequency/status/source_note) is scored. Getting this
pairing right, and keeping it free of the fields it's later used to
score, is the foundation everything in scoring.py depends on.

Identity is normalized medication NAME alone. source_note, status, and
notes are never used to decide who matches whom - see MATCHING_ATTRIBUTES
below for exactly why, and benchmark/README.md's "Medication matching"
section for the real duplicate-group audit this design was checked
against before implementation.
"""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from itertools import permutations
from typing import Any

# Attributes used to disambiguate a duplicate-name group (more than one
# predicted or expected medication sharing the same normalized name
# within one case) - dosage/route/frequency only, per Issue #90's
# explicit design:
#
#   - source_note is excluded because it is itself an independently
#     scored source-attribution field (score_source_note, scoring.py);
#     using it to decide *which* pair is "the match" would make its own
#     accuracy close to 100% by construction - a circular metric.
#   - status is excluded because it is sparse (~27% non-null across the
#     benchmark) and free-form; it should be scored on its own merits,
#     not used to help find its own pairing.
#   - notes is excluded because it's free text, never exact-match scored
#     (score_notes, scoring.py, is presence-only).
#
# Verified against the real benchmark before this was implemented: 6 of
# the dataset's 9 duplicate-containing groups (BENCH-006 atorvastatin,
# BENCH-010 metformin [3-way] and lisinopril, BENCH-022 atorvastatin,
# BENCH-029 lisinopril and furosemide) have dosage/route/frequency
# identical (or entirely null) across every member of the group - the
# only field that actually differs between them is source_note (or, for
# BENCH-006/022's atorvastatin groups, status). Neither is available to
# this matcher, so these specific pairs are inherently undecidable by any
# permitted signal - see AMBIGUOUS PAIRS below for how that is handled
# without silently adding either field back in.
MATCHING_ATTRIBUTES = ("dosage", "route", "frequency")


def normalize_text(value: str | None) -> str | None:
    """Unicode NFC -> strip -> collapse internal whitespace -> casefold.
    None passes through unchanged. Used for every string comparison in
    this module and in scoring.py - the one normalization rule Issue #90
    applies, deliberately excluding punctuation stripping or any
    semantic/alias normalization (see docs/ai.md and benchmark/
    README.md: the ground truth itself preserves wording exactly as the
    source note stated it, so normalizing meaning away here would score
    models against a more lenient contract than the one they were
    actually asked to follow - "PO" and "oral" remain unequal, as do
    "twice daily"/"BID", "10 mg"/"10mg", and "discontinued"/"stopped").
    """
    if value is None:
        return None
    normalized = unicodedata.normalize("NFC", value).strip()
    return " ".join(normalized.split()).casefold()


@dataclass
class MatchedPair:
    expected: dict[str, Any]
    predicted: dict[str, Any]
    # True when this pair came from a duplicate-name group where more
    # than one equally-good assignment existed (every permitted signal -
    # dosage/route/frequency - tied). Every score OTHER than source_note
    # is unaffected by which specific pairing was chosen in that case,
    # since a tie means those fields already agree identically no matter
    # which assignment wins; only source_note accuracy would be affected,
    # so ambiguous pairs are excluded from its denominator entirely
    # (scoring.py's score_source_note) rather than scored right or wrong
    # by what would amount to an arbitrary coin flip.
    source_note_ambiguous: bool


@dataclass
class CaseMatchResult:
    matched: list[MatchedPair]
    false_positives: list[dict[str, Any]]  # unmatched predicted medications
    false_negatives: list[dict[str, Any]]  # unmatched expected medications


def _group_by_name(medications: list[dict[str, Any]]) -> dict[str | None, list[dict[str, Any]]]:
    groups: dict[str | None, list[dict[str, Any]]] = {}
    for medication in medications:
        key = normalize_text(medication.get("name"))
        groups.setdefault(key, []).append(medication)
    return groups


def _agreement_score(predicted: dict[str, Any], expected: dict[str, Any]) -> int:
    """Count of MATCHING_ATTRIBUTES fields that agree after normalization
    - both-null counts as agreement (the two items share the same
    missingness pattern, itself a real signal about which real-world
    medication mention they likely both describe).
    """
    return sum(
        1
        for field in MATCHING_ATTRIBUTES
        if normalize_text(predicted.get(field)) == normalize_text(expected.get(field))
    )


def _best_assignments_within_group(
    predicted_group: list[dict[str, Any]], expected_group: list[dict[str, Any]]
) -> list[tuple[tuple[int, int], ...]]:
    """Every index-pairing achieving the maximum total agreement score for
    this (predicted, expected) duplicate-name group, deduplicated.

    A global search over the whole permutation space, not a greedy
    left-to-right walk - it depends only on the *set* of predicted/
    expected items, never on the order they happened to arrive in. Only
    ever run on groups of a handful of items (the largest in the current
    benchmark is 3), so brute force is cheap by construction.
    """
    pair_count = min(len(predicted_group), len(expected_group))
    if pair_count == 0:
        return []

    best_score = -1
    best_assignments: list[tuple[tuple[int, int], ...]] = []
    seen: set[tuple[tuple[int, int], ...]] = set()

    for pred_subset in permutations(range(len(predicted_group)), pair_count):
        for exp_subset in permutations(range(len(expected_group)), pair_count):
            assignment = tuple(sorted(zip(pred_subset, exp_subset, strict=True)))
            if assignment in seen:
                continue
            seen.add(assignment)

            score = sum(
                _agreement_score(predicted_group[p], expected_group[e]) for p, e in assignment
            )
            if score > best_score:
                best_score = score
                best_assignments = [assignment]
            elif score == best_score:
                best_assignments.append(assignment)

    return best_assignments


def _match_group(
    predicted_group: list[dict[str, Any]], expected_group: list[dict[str, Any]]
) -> tuple[list[MatchedPair], list[dict[str, Any]], list[dict[str, Any]]]:
    """Matches one duplicate-name group. Returns (matched, leftover
    predicted, leftover expected) - leftover items become FP/FN in
    match_case, below.
    """
    if not predicted_group or not expected_group:
        return [], list(predicted_group), list(expected_group)

    best_assignments = _best_assignments_within_group(predicted_group, expected_group)
    # The concrete assignment realized is the canonically-smallest one
    # (sorting the list of equally-good index-pairings themselves) -
    # deterministic given the group's contents, independent of which
    # order permutations happened to be discovered in above.
    chosen = min(best_assignments)

    # A pair is ambiguous unless it appears in *every* optimal
    # assignment - i.e., some other equally-good way of pairing this
    # group would have matched one of its two items differently.
    membership = Counter(pair for assignment in best_assignments for pair in assignment)
    fully_agreed = len(best_assignments)

    matched: list[MatchedPair] = []
    matched_pred_indices: set[int] = set()
    matched_exp_indices: set[int] = set()
    for pred_idx, exp_idx in chosen:
        matched.append(
            MatchedPair(
                expected=expected_group[exp_idx],
                predicted=predicted_group[pred_idx],
                source_note_ambiguous=membership[(pred_idx, exp_idx)] < fully_agreed,
            )
        )
        matched_pred_indices.add(pred_idx)
        matched_exp_indices.add(exp_idx)

    leftover_predicted = [p for i, p in enumerate(predicted_group) if i not in matched_pred_indices]
    leftover_expected = [e for i, e in enumerate(expected_group) if i not in matched_exp_indices]
    return matched, leftover_predicted, leftover_expected


def match_case(
    expected_medications: list[dict[str, Any]], predicted_medications: list[dict[str, Any]]
) -> CaseMatchResult:
    """Matches every medication in one benchmark case. Grouping by
    normalized name first means the common case (no duplicates on either
    side) never touches the permutation-search machinery at all - it's
    only exercised for the handful of groups that actually need it.
    """
    expected_groups = _group_by_name(expected_medications)
    predicted_groups = _group_by_name(predicted_medications)

    matched: list[MatchedPair] = []
    false_positives: list[dict[str, Any]] = []
    false_negatives: list[dict[str, Any]] = []

    for name in sorted(set(expected_groups) | set(predicted_groups), key=lambda n: (n is None, n)):
        pred_group = predicted_groups.get(name, [])
        exp_group = expected_groups.get(name, [])

        if len(pred_group) == 1 and len(exp_group) == 1:
            matched.append(
                MatchedPair(
                    expected=exp_group[0], predicted=pred_group[0], source_note_ambiguous=False
                )
            )
            continue

        group_matched, leftover_pred, leftover_exp = _match_group(pred_group, exp_group)
        matched.extend(group_matched)
        false_positives.extend(leftover_pred)
        false_negatives.extend(leftover_exp)

    return CaseMatchResult(
        matched=matched, false_positives=false_positives, false_negatives=false_negatives
    )
