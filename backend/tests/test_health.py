import re

from app.core.config import settings

UTC_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def test_health_check_ok(client):
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == {"status": "connected"}


def test_health_check_returns_every_documented_field(client):
    # docs/api.md's documented shape, checked field-by-field rather than
    # with a single `==` against the whole body - version/environment/etc.
    # depend on whatever Settings actually resolves to in this process, so
    # this only pins the ones that are fixed by test setup and the shape
    # of the rest.
    response = client.get("/health")
    body = response.json()

    assert set(body.keys()) == {
        "status",
        "version",
        "environment",
        "database",
        "storage",
        "ai",
        "timestamp",
    }
    assert isinstance(body["version"], str) and body["version"]
    assert isinstance(body["environment"], str) and body["environment"]
    assert set(body["storage"].keys()) == {"backend"}
    assert set(body["ai"].keys()) == {"provider", "model"}
    assert UTC_TIMESTAMP_PATTERN.match(body["timestamp"])


def test_health_check_reports_version_from_configuration(client, monkeypatch):
    monkeypatch.setattr(settings, "app_version", "9.9.9")

    response = client.get("/health")

    assert response.json()["version"] == "9.9.9"


def test_health_check_reports_environment_from_configuration(client, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "production")

    response = client.get("/health")

    assert response.json()["environment"] == "production"


def test_health_check_reports_configured_storage_backend(client, monkeypatch):
    monkeypatch.setattr(settings, "storage_backend", "local")

    response = client.get("/health")

    assert response.json()["storage"] == {"backend": "local"}


def test_health_check_reports_s3_storage_backend_without_contacting_s3(client, monkeypatch):
    # No AWS credentials are configured in the test environment at all -
    # if this route ever constructed a real S3StorageService (which calls
    # boto3.client("s3", ...)) or made any request to S3, this would be
    # the test that catches it, since a genuine S3 call here would either
    # hang, raise, or (at minimum) behave very differently from a plain
    # settings read.
    monkeypatch.setattr(settings, "storage_backend", "s3")

    response = client.get("/health")

    assert response.status_code in (200, 503)
    assert response.json()["storage"] == {"backend": "s3"}


def test_health_check_reports_configured_ai_model(client, monkeypatch):
    monkeypatch.setattr(settings, "gemini_model", "gemini-9.9-ultra")

    response = client.get("/health")

    assert response.json()["ai"]["model"] == "gemini-9.9-ultra"


def test_health_check_reports_gemini_as_the_ai_provider(client):
    response = client.get("/health")

    assert response.json()["ai"]["provider"] == "gemini"


def test_health_check_does_not_require_a_gemini_api_key(client, monkeypatch):
    # No AIProvider is ever instantiated (only GeminiProvider.name, a
    # class attribute) - reporting the AI provider/model must not depend
    # on GEMINI_API_KEY being configured, unlike actually using AI
    # features (which fails with a clear 503 - see docs/api.md).
    monkeypatch.setattr(settings, "gemini_api_key", None)

    response = client.get("/health")

    assert response.status_code in (200, 503)
    assert response.json()["ai"]["provider"] == "gemini"


def test_health_check_returns_503_when_database_unavailable(client, monkeypatch):
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise Exception("connection refused")

        def close(self):
            pass

    monkeypatch.setattr("app.api.routes.health.SessionLocal", lambda: BrokenSession())

    response = client.get("/health")

    assert response.status_code == 503

    body = response.json()
    assert body["status"] == "error"
    assert body["database"]["status"] == "disconnected"
    assert body["database"]["detail"] == "connection refused"


def test_health_check_still_reports_version_and_config_when_database_is_down(client, monkeypatch):
    # version/environment/storage/ai never depended on the database to
    # begin with - a down database shouldn't blank them out, and they're
    # arguably more useful, not less, while diagnosing exactly this
    # failure.
    class BrokenSession:
        def execute(self, *args, **kwargs):
            raise Exception("connection refused")

        def close(self):
            pass

    monkeypatch.setattr("app.api.routes.health.SessionLocal", lambda: BrokenSession())
    monkeypatch.setattr(settings, "app_version", "9.9.9")

    response = client.get("/health")
    body = response.json()

    assert body["version"] == "9.9.9"
    assert body["storage"] == {"backend": settings.storage_backend}
    assert body["ai"]["provider"] == "gemini"


def test_health_check_omits_database_detail_when_connected(client):
    response = client.get("/health")

    assert "detail" not in response.json()["database"]
