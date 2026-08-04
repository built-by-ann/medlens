from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MedLens API"
    app_env: str = "development"
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"

    # Comma-separated list of explicitly allowed frontend origins (e.g. a
    # deployed frontend's URL). Local Vite dev servers do not need to be
    # listed here; app.main allows any localhost/127.0.0.1 origin
    # separately, but only outside production.
    cors_allowed_origins: str = ""

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

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()
