import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app


def _register_and_login(client, email, password="correcthorse123"):
    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "username": email.split("@")[0].replace("-", "_")[:30],
            "name": "Logging Test User",
        },
    )

    login_response = client.post("/auth/login", json={"email": email, "password": password})

    return login_response.json()["access_token"]


def _http_request_completed_records(caplog):
    return [r for r in caplog.records if getattr(r, "event", None) == "http_request_completed"]


def test_completed_request_produces_exactly_one_summary_log_line(client, caplog):
    caplog.set_level(logging.INFO)

    client.get("/")

    assert len(_http_request_completed_records(caplog)) == 1


def test_request_summary_includes_method_path_status_and_duration(client, caplog):
    caplog.set_level(logging.INFO)

    client.get("/")

    (record,) = _http_request_completed_records(caplog)
    assert record.method == "GET"
    assert record.path == "/"
    assert record.status_code == 200
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0


def test_request_summary_reflects_a_non_200_status_code(client, caplog):
    caplog.set_level(logging.INFO)

    client.get("/patients/1/clinical-documents")  # no auth -> 401

    (record,) = _http_request_completed_records(caplog)
    assert record.status_code == 401


def test_response_includes_an_x_request_id_header(client):
    response = client.get("/")

    request_id = response.headers.get("X-Request-ID")
    assert request_id is not None
    uuid.UUID(request_id)  # raises ValueError if not a real UUID


def test_x_request_id_header_matches_the_logged_request_id(client, caplog):
    caplog.set_level(logging.INFO)

    response = client.get("/")

    (record,) = _http_request_completed_records(caplog)
    assert record.request_id == response.headers["X-Request-ID"]


def test_two_requests_get_two_different_request_ids(client):
    first = client.get("/")
    second = client.get("/")

    assert first.headers["X-Request-ID"] != second.headers["X-Request-ID"]


def test_health_endpoint_is_excluded_from_request_summary_logging(client, caplog):
    # Polled continuously by Docker's own healthcheck (every 10s, see
    # infra/docker-compose.yml) - a log line for it would be pure noise,
    # never a signal worth an operator's attention.
    caplog.set_level(logging.INFO)

    client.get("/health")

    assert _http_request_completed_records(caplog) == []


def test_request_summary_omits_user_id_for_an_unauthenticated_request(client, caplog):
    caplog.set_level(logging.INFO)

    client.get("/")

    (record,) = _http_request_completed_records(caplog)
    assert record.user_id is None


def test_request_summary_includes_user_id_for_an_authenticated_request(client, caplog):
    token = _register_and_login(client, "middlewareauth@example.com")
    caplog.records.clear()
    caplog.set_level(logging.INFO)

    client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    (record,) = _http_request_completed_records(caplog)
    assert record.user_id is not None


def test_request_id_is_shared_by_every_log_line_within_the_same_request(client, caplog):
    # Proves context propagation, not just that the middleware's own final
    # line has a request_id - a domain-event log fired *during* route
    # handling (login_succeeded) should carry the exact same request_id as
    # the request-summary line that wraps it.
    caplog.set_level(logging.INFO)
    email = "sharedrequestid@example.com"
    client.post(
        "/auth/register",
        json={
            "email": email,
            "password": "correcthorse123",
            "username": "sharedrequestid",
            "name": "Shared Request Id",
        },
    )
    caplog.records.clear()

    client.post("/auth/login", json={"email": email, "password": "correcthorse123"})

    login_records = [r for r in caplog.records if getattr(r, "event", None) == "login_succeeded"]
    summary_records = _http_request_completed_records(caplog)
    assert len(login_records) == 1
    assert len(summary_records) == 1
    assert login_records[0].request_id == summary_records[0].request_id
    assert login_records[0].request_id is not None


def test_request_summary_includes_client_ip(client, caplog):
    caplog.set_level(logging.INFO)

    client.get("/")

    (record,) = _http_request_completed_records(caplog)
    assert record.client_ip is not None


@pytest.mark.parametrize("path", ["/", "/health"])
def test_every_response_still_succeeds_regardless_of_logging(client, path):
    # A sanity check that adding logging never changed a single response's
    # actual behavior - the core "preserve all existing functionality"
    # requirement, checked directly rather than only inferred from every
    # other (unrelated) test file still passing.
    response = client.get(path)

    assert response.status_code == 200


# --- Application lifecycle logging -------------------------------------------


def test_application_startup_is_logged(caplog):
    # TestClient only enters the FastAPI lifespan (app/main.py) when used
    # as a context manager - the shared `client` fixture (conftest.py)
    # deliberately doesn't do that (each test gets its own plain client),
    # so this test drives its own to actually observe startup logging.
    caplog.set_level(logging.INFO)

    with TestClient(app):
        pass

    startup_records = [
        r for r in caplog.records if getattr(r, "event", None) == "application_startup"
    ]
    assert len(startup_records) == 1
    assert startup_records[0].version
    assert startup_records[0].environment


def test_application_shutdown_is_logged(caplog):
    caplog.set_level(logging.INFO)

    with TestClient(app):
        pass

    shutdown_records = [
        r for r in caplog.records if getattr(r, "event", None) == "application_shutdown"
    ]
    assert len(shutdown_records) == 1


# --- Unhandled exception logging ---------------------------------------------


def test_unhandled_exception_is_logged_with_a_traceback_but_the_response_stays_generic(
    caplog, monkeypatch
):
    # raise_server_exceptions=False: Starlette's TestClient otherwise
    # re-raises the original exception in-process for debugging even
    # though ServerErrorMiddleware (where configure_exception_handling's
    # handler actually runs - it wraps *every* middleware, including our
    # own request-logging one) already converted it to a real 500
    # response. Disabling that here is what lets this test observe the
    # actual client-facing response, the same as a real deployment would.
    client = TestClient(app, raise_server_exceptions=False)
    token = _register_and_login(client, "unhandled-exception@example.com")

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated database outage")

    monkeypatch.setattr("app.api.deps.get_user_by_id", _boom)
    caplog.records.clear()
    caplog.set_level(logging.INFO)

    response = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
    # Nothing about the real exception - message, type, or traceback -
    # ever reaches the client (this issue's "Do not expose stack traces or
    # sensitive information to API clients" requirement).
    assert "simulated database outage" not in response.text
    assert "RuntimeError" not in response.text
    assert "Traceback" not in response.text

    (record,) = [r for r in caplog.records if getattr(r, "event", None) == "unhandled_exception"]
    assert record.levelname == "ERROR"
    assert record.exc_info is not None
    assert "simulated database outage" in caplog.text


# --- End-to-end sensitive-data omission --------------------------------------


def test_a_realistic_session_never_logs_credentials_tokens_or_clinical_content(client, caplog):
    # Exercises the exact flow Issue #59's "never log" list is about:
    # register (password), login (issues a JWT used as a Bearer token on
    # every later request), then upload a clinical document whose text
    # names a specific, identifiable condition and medication - the kind
    # of content that must never leave the database and reach a log line,
    # no matter which layer (auth, request logging, document service)
    # touches the request on its way through.
    caplog.set_level(logging.INFO)
    password = "TotallySecretPassw0rd!"
    clinical_text = (
        "Patient reports a history of paranoid schizophrenia, currently "
        "stabilized on clozapine 300mg nightly. Also being treated for "
        "HIV with a daclatasvir regimen."
    )

    token = _register_and_login(client, "sensitive-data-e2e@example.com", password=password)

    patient_response = client.post(
        "/patients",
        json={"first_name": "Jane", "last_name": "Doe", "date_of_birth": "1980-05-14"},
        headers={"Authorization": f"Bearer {token}"},
    )
    patient_id = patient_response.json()["id"]

    document_response = client.post(
        f"/patients/{patient_id}/clinical-documents/upload-txt",
        data={"document_type": "visit_note", "title": "Psychiatric follow-up"},
        files={"file": ("note.txt", clinical_text.encode(), "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert document_response.status_code == 201

    assert password not in caplog.text
    assert token not in caplog.text
    assert f"Bearer {token}" not in caplog.text
    assert "paranoid schizophrenia" not in caplog.text
    assert "clozapine" not in caplog.text
    assert "daclatasvir" not in caplog.text
    assert clinical_text not in caplog.text

    # Sanity check the test actually exercised something worth checking -
    # if these events never fired at all, the assertions above would be
    # vacuously true rather than proof of anything.
    events = {getattr(r, "event", None) for r in caplog.records}
    assert "user_registered" in events
    assert "login_succeeded" in events
    assert "document_uploaded" in events
