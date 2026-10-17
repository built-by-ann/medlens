# Model Evaluation Methodology

How MedLens benchmarks the models it supports for structured medication extraction. Results are in [model-comparison-report.md](model-comparison-report.md). CLI usage, file formats, and algorithms are in `benchmark/README.md`.

## Scope

This measures one capability: extracting medications and their dosage, route, frequency, and status from synthetic clinical notes.

It does **not** evaluate reconciliation, which is deterministic and model-independent (Decision 12). It also doesn't evaluate diagnosis, clinical reasoning, or general medical knowledge.

## Providers

| Provider | Model | Serving |
|---|---|---|
| Gemini | `gemini-2.5-flash` | Hosted API; serving precision and hardware unknown |
| OpenBioLLM | `openbiollm-llama3-instruct` (8B, Q4_K_M) | Local Ollama, with the Llama 3 Instruct template attached via a committed Modelfile |
| MedGemma | `hf.co/bartowski/google_medgemma-4b-it-GGUF:Q4_K_M` (4B) | Local Ollama, using its embedded template |

OpenBioLLM and MedGemma originally ran on Hugging Face hosted inference, which failed with capacity and busy errors before any case was scored. Both were moved to Ollama before any result was accepted. MedGemma also moved from 27B to 4B so it could run locally. This was an infrastructure change, not a quality finding.

## Dataset

- 30 hand-written, fully synthetic cases in `benchmark/cases/`.
- Each case is tagged from a fixed vocabulary (lists, narrative, multi-document, conflicts, dose changes, brand vs. generic, abbreviations, and others) and rated easy, medium, or hard.
- Ground truth is validated against the production `ClinicalSummary` schema on load.

## Protocol

- Every provider gets the **identical prompt** from `build_summary_prompt()` (the same function the app uses). There are no per-provider prompts, system messages, or few-shot examples.
- Local models use `temperature=0` and `seed=0` with no JSON-constrained decoding.
- Parsing has two stages, `json.loads` and then schema validation, so "invalid JSON" and "wrong shape" are distinguishable. Responses are never repaired.
- Failures are classified into fixed categories taken from each provider's real exception boundaries.

## Scoring

**Matching.** Predicted and expected medications are paired by normalized name only. When names repeat, the pairing that maximizes dosage, route, and frequency agreement wins. True ties are marked ambiguous and excluded from `source_note` accuracy. Status, notes, and `source_note` never influence pairing, since they are scored separately.

**Detection (precision, recall, F1)** is reported two ways:

- **End-to-end:** every case counts. Unparseable output scores as an empty prediction, so it produces real false negatives.
- **Conditional on valid output:** only schema-valid cases, reported with their count. This is omitted for providers with zero valid cases.

Zero-denominator convention: precision = 1 when nothing was predicted, and recall = 1 when nothing was expected. Because some cases expect zero medications, a provider with no valid output could still show a nonzero macro F1 or group F1. The report shows those values as **"not applicable"**; the stored metrics are unchanged.

**Attributes.** Dosage, route, frequency, and status use normalized-exact comparison (case and whitespace only, so `PO` ≠ `oral`). Each field reports overall accuracy, accuracy when a value was expected, and the hallucination rate when none was expected.

### Reliability Metrics

Four separate rates, each with its own denominator: call success, JSON validity (of successful calls), schema validity (of valid JSON), and evaluable-case rate (of all cases). A provider can have 100% call success and 0% schema validity.

**Breakdowns.** End-to-end micro F1 by difficulty and by tag, always shown with `n`. Some tags have only 2 cases.

### Latency

Measured over successful calls only. Hosted and local latencies measure different things (network versus local hardware), so they are not comparable.

**Qualitative fields.** `possible_inconsistencies` and `summary` have no ground truth. The report shows excerpts and a frequency count only, never a score or ranking.

## Reproducibility

Each prediction records a `prompt_hash`, and each run records a `benchmark_fingerprint` (a hash of the dataset), model ids, generation parameters, and the Ollama version.

The report can combine providers from different runs only if the fingerprints match and the prompt hashes match for every shared case. Otherwise it fails. A differing `git_commit` only produces a warning. The current report uses Gemini from one run and the local models from another.

## The OpenBioLLM Result

All 30 calls succeeded, and **none produced valid JSON**. This was investigated before being accepted:

- The Modelfile uses Ollama's official Llama 3 Instruct template verbatim.
- The GGUF tokenizer registers the same Llama 3 special tokens at the same indices as the reference model.
- The same prompt sent to reference `llama3:8b-instruct` produced valid output.
- The model card's suggested system persona didn't help.

No single root cause was found. The result stands as an official measurement under this protocol. It does not claim OpenBioLLM can't do extraction in general.

## Limitations

- Only 30 synthetic cases, so this is not a population estimate.
- Exact-match attribute scoring penalizes correct answers phrased differently.
- Quantized local models are compared against a hosted API, so some differences may come from quantization.
- No significance testing or repeated trials.
- Covers medication extraction only.
