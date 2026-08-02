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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]


settings = Settings()
