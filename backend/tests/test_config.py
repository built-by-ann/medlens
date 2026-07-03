from app.core.config import Settings


def test_settings_loads_expected_environment_values(monkeypatch):
    monkeypatch.setenv("APP_NAME", "Test App")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://test_user:test_pass@localhost:5432/test_db"
    )
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
