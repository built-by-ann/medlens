# Model Evaluation Methodology

This document explains how MedLens benchmarks and compares the language models it supports for medication extraction: what is measured, why it is measured that way, and what a result does and does not mean. It is written for a reader assessing whether the evaluation is trustworthy and well-scoped, not for a developer about to run or modify the benchmark code; for exact CLI commands, file formats, and algorithms, see `benchmark/README.md`, which this document links to throughout rather than repeating.

For the current results themselves, see `docs/model-comparison-report.md`. This document contains no run-specific numbers, so it stays accurate independent of when that report was last regenerated.

---

## Purpose and Scope

MedLens uses a language model to read synthetic clinical notes and extract structured, medication-focused information: which medications are mentioned, their dosage/route/frequency/status as stated in the text, and a short summary (see `docs/ai.md`'s AI Philosophy section). This evaluation measures exactly that one capability, structured medication extraction from clinical text, across the providers MedLens supports.

It does not evaluate reconciliation. Comparing extracted medications against a patient's actual medication list is deterministic backend logic that never calls a language model (Decision 12, `docs/design-decisions.md`), so no model choice affects it, and this evaluation says nothing about it. It also does not evaluate general clinical reasoning, diagnosis, or medical knowledge; see Limitations, below.

## Evaluated Providers and Models

Three providers are evaluated, each an `AIProvider` implementation behind the same interface (Decision 15, `docs/design-decisions.md`; see `docs/ai.md`'s Provider Abstraction section for the full architecture):

- **Gemini** (`gemini-2.5-flash`), a hosted API with provider-controlled serving configuration. This project does not know, and does not claim to know, the serving precision or hardware behind it.
- **OpenBioLLM** (`openbiollm-llama3-instruct`), served locally through Ollama: an 8B parameter, Q4_K_M-quantized GGUF, built from a committed Modelfile that attaches the correct Meta Llama 3 Instruct chat template to the upstream weights (see `docs/ai.md`'s Manual Setup section for exactly why that attachment is necessary and how it was verified).
- **MedGemma** (`hf.co/bartowski/google_medgemma-4b-it-GGUF:Q4_K_M`), also served locally through Ollama: a 4B parameter, Q4_K_M-quantized GGUF, used directly since its GGUF already embeds a correct chat template.

## Hosted vs. Local Execution History

OpenBioLLM and MedGemma were not always served locally. Both were originally called through Hugging Face's hosted Inference Providers, and both hosted paths were tested before evaluation began. Both had persistent capacity and availability failures under that hosted path: OpenBioLLM returned `503 capacity_exhausted`, and MedGemma returned "This model is busy, please try again later." Neither had scored a single benchmark case at that point.

The switch to local Ollama inference happened before any official benchmark result was accepted, as a direct response to that operational unreliability. This is an infrastructure change, not a finding about either model's quality: nothing about the hosted failures said anything about how well either model would perform at the actual extraction task, only that the hosted serving path could not be relied on to run the evaluation at all. MedGemma additionally moved from the originally selected 27B hosted checkpoint to a 4B checkpoint suitable for local execution.

## Synthetic Benchmark Dataset and Ground Truth

The benchmark is 30 hand-written cases (`benchmark/cases/`), each a set of one or more synthetic clinical note texts and the medication data that should be extracted from them. All data is entirely synthetic; no case is derived from a real patient record, and none should ever be added that is (Decision 8, `docs/design-decisions.md`).

Every case is tagged from a fixed vocabulary (`benchmark/loader.py`'s `KNOWN_TAGS`) covering scenarios such as straightforward lists, narrative text, multiple documents, conflicting information across documents, dose changes, brand-vs-generic naming, and abbreviations, and is assigned one of three difficulty levels (easy/medium/hard). Ground truth is validated structurally on load, including against the real, production `ClinicalSummary` schema (`benchmark/loader.py`'s `validate_case`), so a ground-truth case can never drift out of the shape the model is actually asked to produce.

## Standardized Prompt and Protocol

Every provider receives the exact same prompt for a given case: `build_summary_prompt()` (`app/ai/prompts.py`), the same function the running application itself uses, is called exactly once per case, and that identical string is sent to every selected provider. No provider receives a custom system prompt, a different phrasing, or any other provider-specific prompt engineering; a `prompt_hash` recorded alongside every prediction proves this (see Reproducibility and Provenance, below).

Chat-template wrapping, the special tokens a local model's own template inserts around a message before generation, is Ollama's responsibility, not the benchmark's. It is deliberately kept separate from the prompt itself: the benchmark never authors or adjusts a model-specific template beyond what is required to expose Ollama's own documented Instruct format for a given checkpoint (see the OpenBioLLM Investigation, below, for the one case where this actually mattered).

## Parsing and Failure Handling

A response is parsed in two explicit stages: `json.loads()`, then `ClinicalSummary.model_validate()` (the same, unmodified schema the application uses), so "not valid JSON at all" and "valid JSON in the wrong shape" are distinguishable outcomes rather than one collapsed failure. Neither stage repairs, completes, or otherwise alters a response; a malformed response is scored as malformed, never fixed up.

Every provider failure is classified into one of a fixed set of categories (missing credential, connection error, model not found, timeout, empty response, a provider-level error, or an unexpected error), derived from the real exception boundaries each `AIProvider` implementation already has, not invented for this evaluation. See `benchmark/README.md`'s "Failure categories" table for the complete list.

## Medication Matching

Before any field is scored, predicted medications are paired with expected medications within a case (`benchmark/metrics/matching.py`). Identity is normalized medication name alone; a medication's `source_note`, `status`, and free-text `notes` are never used to decide which predicted item matches which expected item, since each of those is itself something this evaluation separately scores, and using them to establish the pairing would make that later score circular.

When more than one medication shares a name within a case (a real, audited situation in this dataset), the matcher searches every possible pairing within that name group and picks the one maximizing agreement on dosage, route, and frequency. When more than one pairing ties for best (every permitted signal agrees identically either way), the affected pair is marked ambiguous and excluded from `source_note` accuracy's own denominator rather than scored right or wrong by what would be an arbitrary tie-break.

## End-to-End and Conditional Metrics

Medication detection is scored two ways, both derived from `benchmark/metrics/scoring.py`:

- **End-to-end** counts every attempted case. A response that never parses as valid, schema-conforming JSON is scored as an empty prediction, a real false negative against whatever medications were actually expected, never excluded and never repaired. This is the view that reflects a provider's overall performance under the benchmark protocol, including failures.
- **Conditional on valid output** is computed only over cases where a provider actually produced schema-valid output, isolating extraction quality from reliability. It is reported alongside the count of evaluable cases it was computed from, and is never shown at all for a provider with zero such cases.

Both use a standard information-retrieval convention for a zero-denominator case: precision is 1.0 when nothing was predicted (vacuously precise, since nothing wrong was said), recall is 1.0 when nothing was expected (vacuously complete, since nothing was there to miss), and F1 is 1.0 only when both are, whether genuinely or vacuously, and 0.0 whenever either is a genuine, non-vacuous zero.

This convention has one consequence worth stating plainly: a provider that never produces any evaluable output at all can still show a non-zero macro F1, or a non-zero F1 within a difficulty or tag group, purely because some cases in this dataset genuinely expect zero medications, and "nothing predicted, nothing expected" scores as a vacuous 1.0 for that one case regardless of whether the provider ever produced real output anywhere else. `benchmark/metrics/` (#90) leaves this mathematically correct convention unchanged, since it is the right definition in general; `benchmark/report/` (#91) instead suppresses these specific figures as "not applicable" in its own human-facing display for a provider with zero evaluable cases overall, so a reader is never shown an apparent performance number backed by no real structured output. See `docs/model-comparison-report.md`'s Medication Detection and Difficulty/Tag Breakdown sections for what this looks like on a real result.

## Attribute Metrics

Dosage, route, frequency, and status are each scored with normalized-exact comparison only (whitespace and casing normalized; no semantic or alias normalization, so "PO" and "oral" are not treated as equal). Each field reports three numbers with three different denominators (`score_attribute`, `benchmark/metrics/scoring.py`): overall accuracy, accuracy given the field was actually expected to have a value, and how often a value was invented where none was expected. Splitting these apart matters because a sparse field can otherwise produce a misleadingly high plain accuracy by mostly agreeing on null.

## Reliability Metrics and Their Denominators

Four rates are reported, each over a different population: the share of calls that succeeded at all; the share of successful calls that returned valid JSON; the share of JSON-valid responses that also matched the schema; and the share of all attempted cases that were schema-valid overall (the "evaluable case rate"). These are deliberately never merged into one number, because a provider can have a perfect call-success rate and a zero schema-validity rate at the same time, a real, distinct outcome rather than a contradiction. This combination is not hypothetical; see `docs/model-comparison-report.md`'s Reliability section for a real example of exactly this pattern.

## Difficulty and Tag Breakdowns

End-to-end micro F1 is additionally reported grouped by difficulty level and by tag, always alongside the group's own sample size, so a group's numbers are never read as more statistically meaningful than the sample size actually supports (some tags have as few as 2 cases). The same zero-evaluable-provider caveat from End-to-End and Conditional Metrics applies here too, and at the group level it is sharper: a group made up entirely of zero-expected-medication cases can score a vacuous 100% for a provider that produced no real output at all, so every group cell for such a provider is likewise shown as "not applicable" in the human-facing report.

## Latency

Latency is measured only over successful calls, since a failed call's near-instant latency (for example, a missing-credential check that never reaches the network) is not a measure of a model's or provider's actual speed. It is never treated as hardware-comparable: a hosted API's latency reflects network conditions to that API, while a local Ollama provider's latency reflects whichever machine actually executed the benchmark run. Comparing the two as if they measured the same thing would be a category error, not a finding about either provider's underlying speed.

## Qualitative Fields: possible_inconsistencies and summary

`possible_inconsistencies` and `summary` are part of the same `ClinicalSummary` schema every other field is validated against, but neither is scored quantitatively (`benchmark/metrics/`, #90), because this benchmark defines no ground truth for what an ideal inconsistency list or summary should contain. The comparison report (#91) shows a small, deterministically selected sample of each per provider, described only as illustrative output behavior, for example a raw count of how often a provider's output happened to include a non-empty inconsistency list. That count is a frequency of output behavior, not an accuracy, recall, or sensitivity measurement, and summaries are never ranked or compared for quality across providers.

## Reproducibility and Provenance

Every prediction carries a `prompt_hash` (a hash of the exact prompt string sent for that case) and every run carries a `benchmark_fingerprint` (a hash of the entire loaded dataset's content at the time the run executed), both computed by `benchmark/runner/` (#89) and recorded in `manifest.json`. A run's manifest also records each provider's exact model identifier, inference backend, generation parameters, and (for local providers) the Ollama runtime version.

This is what makes it possible to build one comparison from more than one run directory: `benchmark/report/` (#91) verifies, before rendering anything, that every cited run shares the same `benchmark_fingerprint` and that every case shared across cited runs has an identical `prompt_hash`, failing loudly rather than silently if either check fails. A `git_commit` mismatch across cited runs is surfaced as a warning rather than a hard failure, since an unrelated documentation-only commit between two runs does not itself invalidate a comparison. This is the safeguard that let the actual comparison in `docs/model-comparison-report.md` be built from two separate runs (Gemini from a clean run, OpenBioLLM/MedGemma from a separate run whose own Gemini calls had been affected by an unrelated account issue) without weakening what is being compared.

## The OpenBioLLM Investigation

The official result for OpenBioLLM is that all 30 inference calls completed successfully, and none of the 30 responses produced valid JSON under this benchmark's standardized protocol. This was investigated before being accepted as an official result, not assumed to be either a bug or a finding.

The checks performed did not reveal an obvious adapter or configuration explanation. The local Ollama Modelfile uses Ollama's own official Llama 3 Instruct chat template verbatim, copied directly from Ollama's reference `llama3:8b-instruct-q4_K_M` model rather than hand-transcribed. The OpenBioLLM GGUF's own tokenizer was inspected directly and registers the same Llama 3 special and control tokens, at the same vocabulary indices, as that reference model. A control test sending the identical benchmark prompt, through the identical request configuration, to that reference model produced a correct, schema-valid extraction, while OpenBioLLM did not. The system-role persona message documented in OpenBioLLM's own model card usage example was also tested directly against the same prompt, and did not resolve the behavior either.

**The audit did not establish a single root cause.** This result is retained as an official measurement of OpenBioLLM's behavior under this benchmark's standardized protocol. It has not been repaired, replaced, or discarded, and it is not a claim that OpenBioLLM is universally unable to perform medication extraction, only that it did not produce parseable structured output under this exact protocol, in this exact evaluation.

## Limitations

- **30 synthetic, hand-written cases.** This is not a large-scale or randomly sampled evaluation, and no result should be read as a precise population estimate.
- **Exact-match-oriented scoring.** Attribute comparison is normalized-exact only, with no semantic or alias normalization beyond the fixed medication-matching rules described above; a correct answer phrased differently than the ground truth is scored as incorrect.
- **Quantized local models compared against a hosted API.** OpenBioLLM and MedGemma run as Q4_K_M GGUF quantizations on local hardware; Gemini is a hosted API with provider-controlled serving configuration, and this project does not know its serving precision or hardware. Any quality difference observed may partly reflect quantization rather than only the underlying model.
- **No statistical significance testing.** No confidence intervals, hypothesis tests, or significance claims are computed anywhere in this evaluation; with 30 cases and no repeated trials, none would be meaningful.
- **Medication-reconciliation-focused, not a general clinical-capability benchmark.** This evaluation measures structured medication extraction from clinical notes only. It makes no claim about any provider's broader clinical reasoning, diagnostic ability, or general medical knowledge.

## Where to Find Results

Results are published separately, in `docs/model-comparison-report.md`, kept out of this document so the methodology stays accurate independent of when results were last regenerated. That document is a reviewed, promoted copy of `benchmark/report/`'s own generated output; see `benchmark/README.md`'s "Generating a comparison report" section for exactly how it is produced and how a new comparison can be regenerated from any set of already-scored `benchmark/runner`/`benchmark/metrics` run directories.
