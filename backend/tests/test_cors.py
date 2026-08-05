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


def _build_settings(monkeypatch, app_env: str) -> Settings:
    # Mirrors test_config.py's pattern: a fresh Settings instance from
    # explicit env vars, never the shared app-wide settings singleton, so
    # these tests can exercise multiple environments deterministically and
    # in isolation from whatever the developer's own .env happens to say.
    monkeypatch.setenv("APP_ENV", app_env)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@localhost:5432/db")
    monkeypatch.setenv("JWT_SECRET_KEY", "unit-test-secret")

    return Settings(_env_file=None)


def _build_client(monkeypatch, app_env: str) -> TestClient:
    settings = _build_settings(monkeypatch, app_env)

    app = FastAPI()
    configure_cors(app, settings.app_env)

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


def test_production_allows_no_origin_at_all(monkeypatch):
    # Issue #190: production has no cross-origin allowlist to configure
    # anymore - the deployed frontend reaches the backend exclusively
    # through nginx's same-origin reverse proxy (frontend/nginx.conf),
    # never as a real cross-origin browser request, so there is no
    # legitimate origin production should ever need to allow. A request
    # claiming to be from what used to be a plausible deployed frontend
    # origin must still be rejected, the same as any other origin.
    client = _build_client(monkeypatch, app_env="production")

    response = _preflight(client, "https://app.medlens.example.com")

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
