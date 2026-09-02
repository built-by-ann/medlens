from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MedLens API"
    app_env: str = "development"
    # Issue #61: surfaced by GET /health so a deployed instance's version
    # is checkable without SSHing in to inspect the running image; a
    # plain string, not derived from git or the Docker image tag, since
    # neither is available to the running process today.
    app_version: str = "1.0.0"
    # Issue #59: passed to configure_logging() (app/core/logging_config.py)
    # as the root logger's level. "INFO" surfaces the per-request summary
    # line and every application lifecycle event this issue adds; "DEBUG"
    # would additionally surface third-party libraries' own debug output
    # (SQLAlchemy query logs, etc.), which is why it isn't the default.
    log_level: str = "INFO"
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    # Which AIProvider implementation get_ai_summary_service()
    # (app/ai/service.py) constructs: "gemini" (the default, so an
    # existing deployment with no AI_PROVIDER set keeps working unchanged),
    # "openbiollm", or "medgemma". See the model_validator below for the
    # startup check that keeps this from being anything else, the same
    # "fail at startup, not on first use" treatment storage_backend
    # already gets.
    ai_provider: str = "gemini"

    # Used by both openbiollm and medgemma: both are served locally by an
    # Ollama daemon (see openbiollm_provider.py and medgemma_provider.py),
    # no API key of any kind. This is a plain connection detail, not a
    # secret - kept as a Settings field (rather than a provider constant)
    # since, unlike a generation parameter, it genuinely varies by
    # deployment (e.g. a container reaching Ollama on the host via
    # "http://host.docker.internal:11434"; see infra/docker-compose.yml).
    ollama_base_url: str = "http://localhost:11434"
    # Which local Ollama model to call for OpenBioLLM. Not the raw
    # `hf.co/aaditya/OpenBioLLM-Llama3-8B-GGUF:Q4_K_M` import - that GGUF
    # embeds no usable chat template of its own, so this instead names a
    # local model built from infra/ollama/openbiollm-llama3-instruct
    # .Modelfile, which attaches the correct Meta Llama 3 Instruct
    # template to the same, unmodified weights. See that Modelfile's own
    # comments and openbiollm_provider.py for the full explanation.
    openbiollm_model: str = "openbiollm-llama3-instruct"
    # Which local Ollama model to call for MedGemma. This exact GGUF
    # embeds a correct Gemma-style chat template already, so it's used
    # directly with no Modelfile of its own - see medgemma_provider.py.
    medgemma_model: str = "hf.co/bartowski/google_medgemma-4b-it-GGUF:Q4_K_M"

    # Issue #58: which StorageService implementation
    # app/storage/service.py builds: "local" (the default, zero-config)
    # or "s3". See the model_validator below for what "s3" additionally
    # requires.
    storage_backend: str = "local"
    # Only used by LocalStorageService (app/storage/local.py), where
    # uploaded clinical document files are written on disk. Relative to the
    # backend process's working directory unless given as an absolute path.
    local_storage_dir: str = "./storage/clinical_documents"

    # Only used by S3StorageService (app/storage/s3.py), and only required
    # when storage_backend == "s3"; see the model_validator below.
    aws_region: str | None = None
    s3_bucket_name: str | None = None
    # Deliberately optional even when storage_backend == "s3": the
    # recommended production configuration is an IAM role attached to the
    # EC2 instance (this feature's own "use IAM credentials" requirement),
    # which needs neither of these; boto3 reads the role automatically via
    # instance metadata. These exist only for a developer authenticating
    # with their own AWS credentials to test against a real bucket locally.
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # pydantic-settings' own default is "forbid", not plain pydantic's
        # BaseModel default of "ignore" - discovered the hard way while
        # removing huggingface_api_key below: a real .env file still
        # setting HUGGINGFACE_API_KEY (now unrecognized) made Settings()
        # raise at import time, breaking the whole application, not just
        # AI features. "ignore" makes a stale/unrecognized variable in an
        # existing .env inert instead of a hard startup failure - the
        # same tradeoff that already let this exact scenario happen once.
        extra="ignore",
    )

    @model_validator(mode="after")
    def _validate_s3_configuration(self) -> "Settings":
        """Fails at startup, not on the first upload request, if S3 is
        selected but can't actually be used. Settings() is constructed at
        import time (see settings = Settings() below), so any module that
        imports app.core.config (in practice, the whole application) fails
        to start with this exact message rather than the app coming up
        looking healthy and only breaking on first use.

        aws_access_key_id/aws_secret_access_key are deliberately not
        required here; see their own field comments above.
        """
        if self.storage_backend not in ("local", "s3"):
            raise ValueError(
                f"STORAGE_BACKEND must be 'local' or 's3', got: {self.storage_backend!r}"
            )

        if self.storage_backend == "s3":
            missing = [
                name
                for name, value in (
                    ("AWS_REGION", self.aws_region),
                    ("S3_BUCKET_NAME", self.s3_bucket_name),
                )
                if not value
            ]

            if missing:
                raise ValueError(
                    "STORAGE_BACKEND=s3 requires the following environment "
                    f"variable(s) to be set: {', '.join(missing)}"
                )

        return self

    @model_validator(mode="after")
    def _validate_ai_provider_configuration(self) -> "Settings":
        """Fails at startup, not on the first analysis request, if
        AI_PROVIDER is set to anything get_ai_summary_service() wouldn't
        recognize, the same principle _validate_s3_configuration already
        applies to storage_backend, kept as its own validator since the
        two concerns are unrelated.

        Neither openbiollm nor medgemma require any credential at all -
        both are served by a local Ollama daemon, not a hosted API. If
        Ollama isn't running, or the named model isn't pulled, either
        provider fails with a clear AIProviderError on first use (see
        docs/ai.md's Configuration section) rather than at startup, the
        same "fail on first use, not at import time" tradeoff
        gemini_api_key already makes.
        """
        if self.ai_provider not in ("gemini", "openbiollm", "medgemma"):
            raise ValueError(
                "AI_PROVIDER must be 'gemini', 'openbiollm', or 'medgemma', "
                f"got: {self.ai_provider!r}"
            )

        return self


settings = Settings()
