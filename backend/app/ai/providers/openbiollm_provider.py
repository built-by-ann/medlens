import json
import logging
import time
import urllib.error
import urllib.request

from app.ai.providers.base import AIProvider, AIProviderError
from app.ai.providers.text_cleanup import extract_json_object, strip_code_fences

logger = logging.getLogger(__name__)

# The locally-created Ollama model that attaches the correct Meta Llama 3
# Instruct chat template to the OpenBioLLM-Llama3-8B Q4_K_M GGUF - see
# infra/ollama/openbiollm-llama3-instruct.Modelfile for exactly how it's
# built and why.
#
# Deliberately never the raw `hf.co/aaditya/OpenBioLLM-Llama3-8B-GGUF
# :Q4_K_M` import: that GGUF embeds no usable chat template of its own
# (`ollama show hf.co/aaditya/OpenBioLLM-Llama3-8B-GGUF:Q4_K_M --modelfile`
# reports only `TEMPLATE {{ .Prompt }}`, a bare passthrough with no
# role/turn structure). OpenBioLLM's own model card requires the exact
# Llama 3 Instruct template for correct behavior, since it's a fine-tune
# of Meta-Llama-3-8B-Instruct that was never retrained with a different
# conversational format - verified directly: a manual test against the
# untemplated import asked it to extract a medication from a plain
# clinical sentence, and it reformulated the request as a question
# instead of answering it.
DEFAULT_MODEL = "openbiollm-llama3-instruct"
DEFAULT_BASE_URL = "http://localhost:11434"
# Local CPU/Metal-bound inference on consumer hardware is far slower than
# either hosted provider's response time; 120s is a practical starting
# point for an 8B Q4_K_M model on a single-request, non-streaming call,
# not a measured worst case. Revisit if real benchmark runs show it's too
# tight.
DEFAULT_TIMEOUT_S = 120.0

# Ollama's own runtime name for this integration shape - reported verbatim
# in benchmark reproducibility metadata (see
# benchmark/runner/providers.py's inference_backend_for) so a local run is
# never mistaken for, or silently labeled as, Hugging Face-hosted
# inference.
INFERENCE_BACKEND = "ollama"

# Deterministic generation settings, kept as a provider constant (not
# Settings/.env) since these describe how this one provider is called, not
# deployment configuration - the same reasoning this provider's previous,
# Hugging Face-hosted GENERATION_PARAMS already followed.
#
# Deliberately no `format: "json"` constrained-generation option, even
# though Ollama supports one: #90's benchmark measures this model's own,
# unassisted ability to produce the requested JSON shape, not a
# runtime-enforced grammar - see docs/ai.md's Structured Output section
# and medgemma_provider.py's identical, pre-existing reasoning below.
GENERATION_PARAMS = {"temperature": 0, "seed": 0, "num_predict": 1024}


class OpenBioLLMProvider(AIProvider):
    """OpenBioLLM (aaditya/Llama3-OpenBioLLM-8B), served locally through
    Ollama's HTTP API - no Hugging Face Inference Providers, no hosted
    credential of any kind, no torch/transformers/accelerate in this
    application at all.

    Calls Ollama's `/api/chat` endpoint (not `/api/generate`), which is
    what applies the target model's own chat template automatically. See
    DEFAULT_MODEL's comment above for why that template has to be
    attached via a custom local model rather than relying on the raw GGUF
    import.
    """

    name = "openbiollm"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ):
        self.model = model
        self.base_url = base_url
        self._timeout_s = timeout_s

    def generate_summary(self, prompt: str) -> str:
        started_at = time.monotonic()
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": GENERATION_PARAMS,
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                body = json.loads(response.read())
        except urllib.error.HTTPError as error:
            server_detail = self._read_error_body(error)
            if error.code == 404:
                self._log_failure(started_at, error, reason=server_detail or "model not found")
                raise AIProviderError(
                    f"Ollama model '{self.model}' is not installed. Run: ollama pull {self.model}"
                ) from error
            self._log_failure(started_at, error, reason=server_detail or f"HTTP {error.code}")
            raise AIProviderError(f"OpenBioLLM request failed: HTTP {error.code}") from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, TimeoutError):
                self._log_failure(started_at, error, reason="timeout")
                raise AIProviderError(
                    f"OpenBioLLM request timed out after {self._timeout_s}s"
                ) from error
            self._log_failure(started_at, error, reason="connection failed")
            raise AIProviderError(
                f"Could not connect to Ollama at {self.base_url}. Is the Ollama server running?"
            ) from error
        except TimeoutError as error:
            self._log_failure(started_at, error, reason="timeout")
            raise AIProviderError(
                f"OpenBioLLM request timed out after {self._timeout_s}s"
            ) from error
        except AIProviderError:
            raise
        except Exception as error:
            self._log_failure(started_at, error)
            raise AIProviderError(
                f"Unexpected error calling OpenBioLLM: {type(error).__name__}"
            ) from error

        raw_text = (body.get("message") or {}).get("content")

        if not raw_text:
            self._log_failure(started_at, None, reason="empty response")
            raise AIProviderError("OpenBioLLM returned an empty or invalid response")

        # Strictly syntactic cleanup only - see text_cleanup.py. Never
        # repairs malformed JSON, never infers missing fields, never
        # touches field content; AISummaryService is the only thing that
        # validates the result against ClinicalSummary.
        cleaned_text = extract_json_object(strip_code_fences(raw_text))

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

    @staticmethod
    def _read_error_body(error: urllib.error.HTTPError) -> str | None:
        """Ollama's own error responses are a small JSON object,
        {"error": "..."}. Surfaced only in the server-side log detail via
        _log_failure, never in the AIProviderError message raised to the
        caller.
        """
        try:
            return json.loads(error.read()).get("error")
        except Exception:
            return None

    def _log_failure(
        self, started_at: float, error: Exception | None, reason: str | None = None
    ) -> None:
        duration_ms = (time.monotonic() - started_at) * 1000
        error_type = type(error).__name__ if error is not None else (reason or "unknown")
        detail = self._error_detail(error, reason)
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
        if reason is not None:
            return reason
        if error is None:
            return "unknown"
        return str(error)
