import pytest

from app.core.config import Settings


def test_settings_loads_expected_environment_values(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Test App")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test_user:test_pass@localhost:5432/test_db")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")
    monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "45")

    settings = Settings()

    assert settings.app_name == "Test App"
    assert settings.app_env == "test"
    assert settings.database_url == "postgresql://test_user:test_pass@localhost:5432/test_db"
    assert settings.jwt_secret_key == "unit-test-secret"
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_access_token_expire_minutes == 45


def test_settings_applies_defaults_when_optional_values_unset(monkeypatch):
    monkeypatch.delenv("APP_NAME", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("JWT_ALGORITHM", raising=False)
    monkeypatch.delenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret")

    settings = Settings(_env_file=None)

    assert settings.app_name == "MedLens API"
    assert settings.app_env == "development"
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_access_token_expire_minutes == 30
    assert settings.gemini_model == "gemini-2.5-flash"
    assert settings.storage_backend == "local"


# --- storage_backend validation (Issue #58) ---


def _base_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret")


def test_settings_defaults_to_local_storage_with_no_aws_configuration(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)

    settings = Settings(_env_file=None)

    assert settings.storage_backend == "local"


def test_settings_accepts_s3_when_fully_configured(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "medlens-documents")

    settings = Settings(_env_file=None)

    assert settings.storage_backend == "s3"
    assert settings.aws_region == "us-east-1"
    assert settings.s3_bucket_name == "medlens-documents"


def test_settings_accepts_s3_without_explicit_credentials(monkeypatch):
    # The production-recommended configuration (an IAM role attached to
    # the EC2 instance, this feature's own "use IAM credentials"
    # requirement) supplies no static access key at all - Settings must
    # not require one.
    _base_env(monkeypatch)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_BUCKET_NAME", "medlens-documents")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.aws_access_key_id is None
    assert settings.aws_secret_access_key is None


def test_settings_raises_at_construction_when_s3_selected_with_no_region_or_bucket(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)

    with pytest.raises(ValueError, match=r"AWS_REGION.*S3_BUCKET_NAME"):
        Settings(_env_file=None)


def test_settings_raises_at_construction_when_s3_selected_with_only_region_set(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.delenv("S3_BUCKET_NAME", raising=False)

    with pytest.raises(ValueError, match="S3_BUCKET_NAME"):
        Settings(_env_file=None)


def test_settings_rejects_an_unrecognized_storage_backend(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("STORAGE_BACKEND", "azure_blob")

    with pytest.raises(ValueError, match="STORAGE_BACKEND"):
        Settings(_env_file=None)


# --- ai_provider validation (Issue #87) ---


def test_settings_defaults_to_gemini_with_no_ai_provider_configured(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.delenv("AI_PROVIDER", raising=False)

    settings = Settings(_env_file=None)

    assert settings.ai_provider == "gemini"


def test_settings_accepts_openbiollm_as_ai_provider(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openbiollm")
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "hf-fake-key")

    settings = Settings(_env_file=None)

    assert settings.ai_provider == "openbiollm"
    assert settings.huggingface_api_key == "hf-fake-key"
    assert settings.openbiollm_model == "aaditya/Llama3-OpenBioLLM-8B"


def test_settings_accepts_openbiollm_without_a_huggingface_api_key(monkeypatch):
    # Mirrors gemini_api_key's own optionality: selecting a provider with
    # no credential configured yet must not block the application from
    # starting - only the first actual analysis request should fail, with
    # a clear AIProviderError, exactly like Gemini's missing-key case.
    _base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "openbiollm")
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)

    settings = Settings(_env_file=None)

    assert settings.huggingface_api_key is None


def test_settings_rejects_an_unsupported_ai_provider(monkeypatch):
    _base_env(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER", "chatgpt")

    with pytest.raises(ValueError, match="AI_PROVIDER"):
        Settings(_env_file=None)
