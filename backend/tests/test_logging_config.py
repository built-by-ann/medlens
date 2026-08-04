import json
import logging
from types import SimpleNamespace

import pytest

from app.core.logging_config import (
    ConsoleFormatter,
    JSONFormatter,
    RequestContextFilter,
    _request_context,
    configure_logging,
    get_request_id,
    set_request_user_id,
)


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """configure_logging() (tested directly below) mutates the process-wide
    root logger - app/main.py already calls it once at import time with the
    real Settings, and every other test file's log-based assertions
    (caplog, etc.) depend on that configuration staying intact. Without
    this, whichever configure_logging(...) call this file's tests happen
    to make *last* would silently become the configuration every other
    test file sees, however this file happens to be ordered relative to
    them.
    """
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level

    yield

    root_logger.handlers = original_handlers
    root_logger.setLevel(original_level)


def _make_record(
    message="hello",
    level=logging.INFO,
    logger_name="app.some.module",
    extra: dict | None = None,
    exc_info=None,
) -> logging.LogRecord:
    record = logging.LogRecord(
        name=logger_name,
        level=level,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=exc_info,
    )
    for key, value in (extra or {}).items():
        setattr(record, key, value)
    return record


# --- JSONFormatter -----------------------------------------------------------


def test_json_formatter_emits_valid_json_with_base_fields():
    record = _make_record(message="Login succeeded", extra={"event": "login_succeeded"})

    payload = json.loads(JSONFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.some.module"
    assert payload["event"] == "login_succeeded"
    assert payload["message"] == "Login succeeded"
    assert "timestamp" in payload


def test_json_formatter_timestamp_is_utc_iso8601_with_z_suffix():
    record = _make_record()

    payload = json.loads(JSONFormatter().format(record))

    # e.g. "2026-08-05T02:15:30.123Z" - no "+00:00", no naive/local offset.
    assert payload["timestamp"].endswith("Z")
    assert "+" not in payload["timestamp"]


def test_json_formatter_falls_back_to_message_as_event_when_event_not_set():
    record = _make_record(message="Something happened")

    payload = json.loads(JSONFormatter().format(record))

    assert payload["event"] == "Something happened"


def test_json_formatter_includes_allowed_extra_fields():
    record = _make_record(
        extra={
            "event": "document_uploaded",
            "patient_id": 42,
            "document_id": 7,
            "user_id": 3,
        }
    )

    payload = json.loads(JSONFormatter().format(record))

    assert payload["patient_id"] == 42
    assert payload["document_id"] == 7
    assert payload["user_id"] == 3


def test_json_formatter_omits_a_field_not_in_the_allowlist():
    # The core safety property this issue's "never log passwords/tokens/..."
    # requirement rests on: even if a call site passed something sensitive
    # via extra= under an unexpected key, it simply never reaches the
    # formatted output unless that key is also added to ALLOWED_FIELDS - a
    # deliberate, reviewable step (see app/core/logging_config.py).
    record = _make_record(extra={"event": "test_event", "password": "hunter2"})

    output = JSONFormatter().format(record)
    payload = json.loads(output)

    assert "password" not in payload
    assert "hunter2" not in output


def test_json_formatter_omits_none_valued_fields():
    record = _make_record(extra={"event": "test_event", "patient_id": None})

    payload = json.loads(JSONFormatter().format(record))

    assert "patient_id" not in payload


def test_json_formatter_includes_exception_traceback_when_present():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record(message="Unhandled exception", exc_info=sys.exc_info())

    payload = json.loads(JSONFormatter().format(record))

    assert "exception" in payload
    assert "ValueError: boom" in payload["exception"]


# --- ConsoleFormatter ----------------------------------------------------------


def test_console_formatter_produces_a_single_readable_line():
    record = _make_record(
        message="Login succeeded",
        extra={"event": "login_succeeded", "user_id": 5},
    )

    line = ConsoleFormatter().format(record)

    assert "\n" not in line
    assert "INFO" in line
    assert "event=login_succeeded" in line
    assert "user_id=5" in line


def test_console_formatter_omits_a_field_not_in_the_allowlist():
    record = _make_record(extra={"event": "test_event", "jwt_token": "secret.token.value"})

    line = ConsoleFormatter().format(record)

    assert "secret.token.value" not in line


def test_console_formatter_appends_traceback_on_its_own_lines():
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        record = _make_record(message="Unhandled exception", exc_info=sys.exc_info())

    line = ConsoleFormatter().format(record)

    assert "\n" in line
    assert "ValueError: boom" in line


# --- RequestContextFilter / context propagation -------------------------------


def test_request_context_filter_injects_context_fields():
    token = _request_context.set(
        {"request_id": "abc-123", "method": "GET", "path": "/patients", "client_ip": "127.0.0.1"}
    )
    try:
        record = _make_record()
        RequestContextFilter().filter(record)

        assert record.request_id == "abc-123"
        assert record.method == "GET"
        assert record.path == "/patients"
        assert record.client_ip == "127.0.0.1"
    finally:
        _request_context.reset(token)


def test_request_context_filter_defaults_to_none_outside_a_request():
    token = _request_context.set(None)
    try:
        record = _make_record()
        RequestContextFilter().filter(record)

        assert record.request_id is None
    finally:
        _request_context.reset(token)


def test_request_context_filter_never_overrides_an_explicitly_set_field():
    token = _request_context.set({"request_id": "from-context"})
    try:
        record = _make_record(extra={"request_id": "explicitly-set"})
        RequestContextFilter().filter(record)

        assert record.request_id == "explicitly-set"
    finally:
        _request_context.reset(token)


def test_set_request_user_id_sets_it_on_request_state():
    # A plain object with a `.state` attribute stands in for a real
    # fastapi.Request here - set_request_user_id only ever touches
    # request.state, deliberately *not* the _request_context ContextVar
    # (see its docstring in app/core/logging_config.py for why a
    # ContextVar can't carry user_id reliably across a sync dependency
    # boundary in this codebase).
    request = SimpleNamespace(state=SimpleNamespace())

    set_request_user_id(request, 99)

    assert request.state.user_id == 99


def test_get_request_id_returns_none_outside_a_request():
    token = _request_context.set(None)
    try:
        assert get_request_id() is None
    finally:
        _request_context.reset(token)


def test_get_request_id_returns_the_context_value():
    token = _request_context.set({"request_id": "abc-123"})
    try:
        assert get_request_id() == "abc-123"
    finally:
        _request_context.reset(token)


# --- configure_logging ---------------------------------------------------------


def test_configure_logging_uses_json_formatter_outside_development():
    configure_logging("production", "INFO")

    handler = logging.getLogger().handlers[0]
    assert isinstance(handler.formatter, JSONFormatter)


def test_configure_logging_uses_console_formatter_in_development():
    configure_logging("development", "INFO")

    handler = logging.getLogger().handlers[0]
    assert isinstance(handler.formatter, ConsoleFormatter)


def test_configure_logging_sets_the_root_logger_level():
    configure_logging("production", "WARNING")

    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_installs_the_request_context_filter():
    configure_logging("production", "INFO")

    handler = logging.getLogger().handlers[0]
    assert any(isinstance(f, RequestContextFilter) for f in handler.filters)
