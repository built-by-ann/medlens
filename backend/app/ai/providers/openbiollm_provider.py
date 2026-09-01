import logging
import re
import time

from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError, ValidationError

from app.ai.providers.base import AIProvider, AIProviderError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "aaditya/Llama3-OpenBioLLM-8B"

# The one Hugging Face Inference Provider currently serving this exact
# checkpoint - verified directly against Hugging Face's own API while
# implementing this issue:
#
#   GET https://huggingface.co/api/models/aaditya/Llama3-OpenBioLLM-8B
#       ?expand[]=inferenceProviderMapping
#   -> {"featherless-ai": {"status": "live", "task": "text-generation", ...}}
#
# Pinned explicitly rather than provider="auto" (huggingface_hub's
# default): "auto" resolves to whichever provider HF's routing considers
# fastest at request time, which could silently change to a different
# backend if HF's provider landscape changes - a real problem for the
# benchmark reproducibility #89 depends on, where the same case run twice
# should mean the same weights served the same way both times. Pinning
# here means a change on Hugging Face's side (this provider dropping the
# model) surfaces as a loud, immediate AIProviderError instead of a silent
# switch to a different inference backend.
INFERENCE_PROVIDER = "featherless-ai"

DEFAULT_TIMEOUT_S = 30.0

# Generation parameters for OpenBioLLMProvider, chosen for structured
# extraction rather than open-ended text generation. Kept as constants
# here (not Settings/.env) since these describe how this one provider is
# called, not deployment configuration - the same reasoning
# GeminiProvider.DEFAULT_TIMEOUT_MS already follows for its own timeout.
#
# #89's evaluation framework should record these exact values alongside
# any benchmark results run against this provider, since changing them
# would change what's actually being measured.
GENERATION_PARAMS = {
    # Large enough to hold a full ClinicalSummary JSON response (a
    # medications list, possible_inconsistencies, and a summary) for a
    # multi-document, multi-medication analysis without truncating
    # mid-object. Not tuned empirically - a conservative upper bound.
    "max_new_tokens": 1024,
    # Greedy decoding - the closest thing to deterministic output this
    # API exposes. Appropriate for a structured-extraction task with one
    # intended correct answer per input, unlike creative generation.
    # temperature/top_p/top_k are deliberately left unset: they only
    # affect sampling, which is disabled here.
    "do_sample": False,
    # Only the generated continuation, never the echoed prompt. The
    # prompt itself never contains JSON, but concatenating it back onto
    # the response would make the boundary-finding cleanup below
    # unnecessarily fragile for no benefit.
    "return_full_text": False,
}

_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _strip_code_fences(text: str) -> str:
    """Removes a single markdown code fence wrapping the text, if present.

    Purely syntactic: if a fence is found, its contents are returned
    verbatim with no other change; if not, the text is returned
    unchanged. Never inspects or alters what's inside a fence beyond
    removing the fence markers themselves.
    """
    match = _CODE_FENCE_RE.search(text)
    return match.group(1) if match else text


def _extract_json_object(text: str) -> str:
    """Trims text before the first '{' and after the last '}'.

    This is a boundary-finding operation, not a parser or a repair step:
    it never checks that what's between those two characters is
    well-formed JSON, and never adds, removes, or reorders anything
    within that span. Malformed JSON in the model's output is still
    exactly as malformed after this call - ClinicalSummary.
    model_validate_json() (AISummaryService, not this provider) remains
    the only thing that actually validates the result.
    """
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end < start:
        return text.strip()

    return text[start : end + 1]


class OpenBioLLMProvider(AIProvider):
    """OpenBioLLM (aaditya/Llama3-OpenBioLLM-8B), called through Hugging
    Face's hosted Inference Providers - no local model weights, and no
    torch/transformers/accelerate in this application at all. See the
    module docstring-equivalent comments above for the exact provider
    and generation configuration, verified while implementing this issue.
    """

    name = "openbiollm"

    def __init__(
        self,
        api_key: str | None,
        model: str = DEFAULT_MODEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ):
        self.model = model
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._client: InferenceClient | None = None

    def _get_client(self) -> InferenceClient:
        # The key is checked here, not in __init__, so constructing this
        # provider (for dependency injection) always succeeds - mirrors
        # GeminiProvider._get_client exactly, for the same reason: the
        # missing-credential case should surface as an AIProviderError
        # only when a summary is actually requested.
        if not self._api_key:
            raise AIProviderError("Hugging Face API key is not configured")

        if self._client is None:
            self._client = InferenceClient(
                provider=INFERENCE_PROVIDER,
                token=self._api_key,
                timeout=self._timeout_s,
            )

        return self._client

    def generate_summary(self, prompt: str) -> str:
        started_at = time.monotonic()

        try:
            client = self._get_client()
            raw_text = client.text_generation(
                prompt,
                model=self.model,
                **GENERATION_PARAMS,
            )
        except AIProviderError:
            raise
        except (InferenceTimeoutError, HfHubHTTPError, ValidationError) as error:
            self._log_failure(started_at, error)
            raise AIProviderError(f"OpenBioLLM request failed: {type(error).__name__}") from error
        except Exception as error:
            self._log_failure(started_at, error)
            raise AIProviderError(
                f"Unexpected error calling OpenBioLLM: {type(error).__name__}"
            ) from error

        if not raw_text:
            self._log_failure(started_at, None, reason="empty response")
            raise AIProviderError("OpenBioLLM returned an empty or invalid response")

        # Strictly syntactic cleanup only - see the two helpers' own
        # docstrings above. Never repairs, never touches field content.
        # AISummaryService._parse_response is still the only thing that
        # validates the result against ClinicalSummary.
        cleaned_text = _extract_json_object(_strip_code_fences(raw_text))

        duration_ms = (time.monotonic() - started_at) * 1000
        logger.info(
            "AI request succeeded",
            extra={
                "event": "ai_request_succeeded",
                "provider": self.name,
                "model": self.model,
                "duration_ms": round(duration_ms, 1),
            },
        )

        return cleaned_text

    def _log_failure(
        self, started_at: float, error: Exception | None, reason: str | None = None
    ) -> None:
        duration_ms = (time.monotonic() - started_at) * 1000
        error_type = type(error).__name__ if error is not None else (reason or "unknown")
        detail = self._error_detail(error, reason)

        # Same split as GeminiProvider._log_failure: detail is server-side
        # log only, never included in the AIProviderError message raised
        # above (which is what _safe_error_message, app/api/routes/
        # analyses.py, lets reach the frontend). The Hugging Face token is
        # sent as a request header, never in a URL or exception message,
        # and neither the prompt nor any clinical text is ever passed to
        # this method or logged anywhere.
        logger.warning(
            "AI request failed: %s",
            detail,
            extra={
                "event": "ai_request_failed",
                "provider": self.name,
                "model": self.model,
                "duration_ms": round(duration_ms, 1),
                "error_type": error_type,
            },
        )

    @staticmethod
    def _error_detail(error: Exception | None, reason: str | None) -> str:
        if error is None:
            return reason or "unknown"

        return str(error)
