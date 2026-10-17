# MedLens: Product Requirements

**Version:** 2.0 · **Author:** Ann Mathew · **Status:** MVP implemented and deployed. This records the original scope. See `README.md` for current features and [roadmap.md](roadmap.md) for what remains.

## Problem

A patient's medications are documented in many places: medication lists, visit notes, discharge summaries, progress notes, and reconciliation forms. Those sources drift apart. A drug may be active in one, discontinued in another, and missing from a third. Finding these gaps by hand is slow and error-prone.

MedLens was inspired by research at Vanderbilt University Medical Center on medication documentation inconsistencies in EHRs. It extracts structured medication data from synthetic clinical documents, compares it across sources, and surfaces evidence-backed discrepancies for human review.

It is an educational engineering project, not a clinical tool.

## Goals

- A production-quality full-stack application built with modern engineering practices
- AI extraction of medications from clinical documents
- Comparison across sources, with discrepancies explained using evidence
- Saved analyses for later review

## Non-Goals

Replacing clinicians, giving medical advice, diagnosing or recommending treatment, automatically modifying records, handling real patient data, or acting as an EHR.

## Users

The primary audience is students, researchers, and developers exploring AI-assisted clinical workflows. The secondary audience is recruiters and educators evaluating the project.

## MVP Scope

| Area | Capabilities |
|---|---|
| Auth | Register, log in, protected pages |
| Documents | Upload PDF or text, or paste text. Supports medication lists, visit notes, discharge summaries, and progress notes. View past uploads. |
| Extraction | Medication name, dose, frequency, route, and status, with supporting context, normalized for comparison |
| Analysis | Select multiple documents, run an analysis, and review discrepancies with explanations and evidence. Analyses are saved. |
| Dashboard | Review and delete past analyses, documents, and summaries |

## Success Criteria

A user can register, log in, upload several synthetic documents, run an analysis, review extracted medications and evidence-backed discrepancies, and come back later to the saved analysis.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Hallucinated or incorrect extraction | Structured JSON output, strict Pydantic validation, evidence shown with each finding |
| Normalization errors and false positives | Deterministic comparison rules; a human reviews every finding |
| API changes, auth bugs, deployment issues | Automated tests, structured logging |

## Ethics

The app uses synthetic data only. It is not HIPAA compliant, gives no medical advice, never modifies patient records, and presents AI findings for human review only.

## Future Ideas

FHIR import and export, RxNorm, a medication timeline view, search across analyses, PDF/CSV/JSON export, background jobs, and observability dashboards.
