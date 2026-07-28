from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import configure_cors

ALLOWED_LOCALHOST_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://127.0.0.1:3000",
]

UNTRUSTED_ORIGIN = "http://evil.example.com"


def _build_settings(monkeypatch, app_env: str, cors_allowed_origins: str = "") -> Settings:
    # Mirrors test_config.py's pattern: a fresh Settings instance from
    # explicit env vars, never the shared app-wide settings singleton, so
    # these tests can exercise multiple environments deterministically and
    # in isolation from whatever the developer's own .env happens to say.
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", cors_allowed_origins)

    return Settings(_env_file=None)


def _build_client(monkeypatch, app_env: str, cors_allowed_origins: str = "") -> TestClient:
    settings = _build_settings(monkeypatch, app_env, cors_allowed_origins)

    app = FastAPI()
    configure_cors(app, settings.app_env, settings.cors_allowed_origins_list)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return TestClient(app)


def _preflight(client: TestClient, origin: str):
    return client.options(
        "/ping",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )


def test_development_allows_localhost_on_multiple_ports(monkeypatch):
    client = _build_client(monkeypatch, app_env="development")

    for origin in ALLOWED_LOCALHOST_ORIGINS:
        response = _preflight(client, origin)

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin


def test_development_preflight_returns_expected_cors_headers(monkeypatch):
    client = _build_client(monkeypatch, app_env="development")

    response = _preflight(client, "http://localhost:5173")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "GET" in response.headers["access-control-allow-methods"]


def test_development_rejects_untrusted_origin_preflight(monkeypatch):
    client = _build_client(monkeypatch, app_env="development")

    response = _preflight(client, UNTRUSTED_ORIGIN)

    # Starlette's CORSMiddleware answers a preflight for a disallowed origin
    # with 400 and no CORS headers at all, rather than a 200 that merely
    # omits Access-Control-Allow-Origin.
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_development_actual_request_includes_allow_origin_for_localhost(monkeypatch):
    client = _build_client(monkeypatch, app_env="development")

    response = client.get("/ping", headers={"Origin": "http://localhost:5174"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5174"


def test_development_actual_request_omits_allow_origin_for_untrusted_origin(monkeypatch):
    client = _build_client(monkeypatch, app_env="development")

    # A real (non-preflight) request from a disallowed origin is not itself
    # blocked, since the app still executes and returns 200: what CORS
    # actually prevents is the requesting browser's JS from reading the
    # response, which happens by omitting this header, not by refusing to
    # respond.
    response = client.get("/ping", headers={"Origin": UNTRUSTED_ORIGIN})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_production_disables_localhost_wildcard(monkeypatch):
    client = _build_client(monkeypatch, app_env="production")

    for origin in ALLOWED_LOCALHOST_ORIGINS:
        response = _preflight(client, origin)

        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers


def test_production_still_allows_explicitly_configured_origins(monkeypatch):
    # Confirms production isn't "nothing works", only that the localhost
    # convenience rule is gone; an explicitly configured deployed frontend
    # origin must still be allowed.
    client = _build_client(
        monkeypatch,
        app_env="production",
        cors_allowed_origins="https://app.medlens.example.com",
    )

    response = _preflight(client, "https://app.medlens.example.com")

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://app.medlens.example.com"

    # And localhost is still rejected even with an explicit origin configured.
    localhost_response = _preflight(client, "http://localhost:5173")
    assert localhost_response.status_code == 400
