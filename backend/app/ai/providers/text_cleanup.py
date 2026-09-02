import re

# Shared by every provider whose underlying model returns plain generated
# text rather than a schema-constrained response (OpenBioLLM, MedGemma);
# extracted out of openbiollm_provider.py (Issue #87) when MedGemmaProvider
# (Issue #88) needed the exact same behavior, rather than duplicating it.
# GeminiProvider needs none of this: JSON_RESPONSE_CONFIG
# (gemini_provider.py) already constrains its output to valid JSON.
#
# Both functions are strictly syntactic. Allowed: strip a markdown code
# fence, strip prose outside the outermost JSON object. Not allowed:
# repair malformed JSON, add missing braces, or touch anything inside the
# object. AISummaryService._parse_response (ClinicalSummary.
# model_validate_json) remains the only thing that actually validates a
# provider's response; these functions only decide what string reaches it.

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def strip_code_fences(text: str) -> str:
    """Removes a single markdown code fence wrapping the text, if present.

    If a fence is found, its contents are returned verbatim with no other
    change; if not, the text is returned unchanged. Never inspects or
    alters what's inside a fence beyond removing the fence markers
    themselves.
    """
    match = _CODE_FENCE_RE.search(text)
    return match.group(1) if match else text


def extract_json_object(text: str) -> str:
    """Trims text before the first '{' and after the last '}'.

    This is a boundary-finding operation, not a parser or a repair step:
    it never checks that what's between those two characters is
    well-formed JSON, and never adds, removes, or reorders anything
    within that span. Malformed JSON in the model's output is still
    exactly as malformed after this call.

    Falls back to returning the text unchanged (stripped of surrounding
    whitespace) if no closing brace exists anywhere; a missing boundary
    is never guessed at or invented.
    """
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        return text.strip()

    return text[start : end + 1]
