from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MedLens API"
    app_env: str = "development"
    # Issue #61: surfaced by GET /health so a deployed instance's version
    # is checkable without SSHing in to inspect the running image - a
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
    # (app/ai/service.py) constructs - "gemini" (the default, so an
    # existing deployment with no AI_PROVIDER set keeps working unchanged),
    # "openbiollm", or "medgemma". See the model_validator below for the
    # startup check that keeps this from being anything else - the same
    # "fail at startup, not on first use" treatment storage_backend
    # already gets.
    ai_provider: str = "gemini"

    # Used by both openbiollm and medgemma (both call Hugging Face's
    # Inference Providers mechanism - see openbiollm_provider.py and
    # medgemma_provider.py) - a Hugging Face user access token
    # (fine-grained, scoped to "Make calls to Inference Providers")
    # authenticating every call to either provider. Not required while
    # ai_provider == "gemini" (the default), so an existing deployment
    # needs no new configuration at all.
    huggingface_api_key: str | None = None
    # Which OpenBioLLM checkpoint to call, and the one Hugging Face
    # currently reports as actually served (via the featherless-ai
    # Inference Provider - see openbiollm_provider.py). A plain
    # environment variable, matching gemini_model's own reasoning: if this
    # exact checkpoint is ever retired or moved to a different provider,
    # recovering shouldn't require a code change.
    openbiollm_model: str = "aaditya/Llama3-OpenBioLLM-8B"
    # Which MedGemma checkpoint to call, and the only one Hugging Face
    # currently serves through any Inference Provider (via featherless-ai
    # - see medgemma_provider.py's own comments for why this exact
    # checkpoint, and not one of the 4B variants, was chosen). Gated under
    # Google's "Health AI Developer Foundations" license - see docs/ai.md
    # for the manual account-level prerequisite this requires.
    medgemma_model: str = "google/medgemma-27b-text-it"

    # Issue #58: which StorageService implementation
    # app/storage/service.py builds - "local" (the default, zero-config)
    # or "s3". See the model_validator below for what "s3" additionally
    # requires.
    storage_backend: str = "local"
    # Only used by LocalStorageService (app/storage/local.py) - where
    # uploaded clinical document files are written on disk. Relative to the
    # backend process's working directory unless given as an absolute path.
    local_storage_dir: str = "./storage/clinical_documents"

    # Only used by S3StorageService (app/storage/s3.py), and only required
    # when storage_backend == "s3" - see the model_validator below.
    aws_region: str | None = None
    s3_bucket_name: str | None = None
    # Deliberately optional even when storage_backend == "s3": the
    # recommended production configuration is an IAM role attached to the
    # EC2 instance (this feature's own "use IAM credentials" requirement),
    # which needs neither of these - boto3 reads the role automatically via
    # instance metadata. These exist only for a developer authenticating
    # with their own AWS credentials to test against a real bucket locally.
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @model_validator(mode="after")
    def _validate_s3_configuration(self) -> "Settings":
        """Fails at startup, not on the first upload request, if S3 is
        selected but can't actually be used - Settings() is constructed at
        import time (see settings = Settings() below), so any module that
        imports app.core.config (in practice, the whole application) fails
        to start with this exact message rather than the app coming up
        looking healthy and only breaking on first use.

        aws_access_key_id/aws_secret_access_key are deliberately not
        required here - see their own field comments above.
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
        recognize - the same principle _validate_s3_configuration already
        applies to storage_backend, kept as its own validator since the
        two concerns are unrelated.

        Deliberately does not require huggingface_api_key even when
        ai_provider is "openbiollm" or "medgemma": both providers already
        fail with a clear AIProviderError on first use if it's missing
        (mirroring how gemini_api_key is optional at the application
        level too - see docs/ai.md's Configuration section), so a
        developer can select either without a token yet and see every
        other feature work normally, the same tradeoff already made for
        Gemini.
        """
        if self.ai_provider not in ("gemini", "openbiollm", "medgemma"):
            raise ValueError(
                "AI_PROVIDER must be 'gemini', 'openbiollm', or 'medgemma', "
                f"got: {self.ai_provider!r}"
            )

        return self


settings = Settings()
