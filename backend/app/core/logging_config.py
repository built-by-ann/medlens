"""Central structured-logging setup (Issue #59).

Every application logger (`logging.getLogger(__name__)`, used exactly the
same way it already was before this issue - see Decision 22 in
docs/design-decisions.md) propagates to the root logger, which this module
configures once, at process startup, with a single handler and one of two
formatters chosen by `Settings.app_env`. Nothing elsewhere needs its own
handler, formatter, or `logging.basicConfig(...)` call - "configure
logging centrally rather than individually inside modules" is enforced
simply by there being exactly one place (`configure_logging`, called once
from app/main.py) that ever touches handler/formatter setup at all.
"""

import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Every field a log record is allowed to carry beyond the base
# timestamp/level/logger/event/message set (see JSONFormatter/ConsoleFormatter
# below), each populated either automatically (see RequestContextFilter) or
# explicitly via `extra={...}` at a specific call site (grep the backend for
# `extra=` to see every one). This is an *allowlist*, not just documentation:
# a field name that isn't in this tuple is silently dropped by both
# formatters, even if some future call site passes it via `extra=` - a
# deliberate safety boundary (see Decision 22) so a mistaken `extra={"password":
# ...}` somewhere down the line can never actually reach a log line without
# also being added here first, a visible, reviewable step.
ALLOWED_FIELDS = (
    "event",
    "request_id",
    "method",
    "path",
    "status_code",
    "duration_ms",
    "client_ip",
    "user_id",
    "patient_id",
    "analysis_id",
    "document_id",
    "file_type",
    "provider",
    "model",
    "error_type",
    "storage_key",
    "version",
    "environment",
    "storage_backend",
)

# Paths excluded from the one-line-per-request summary the middleware below
# emits. /health is polled continuously by Docker's own healthcheck (every
# 10s, see infra/docker-compose.yml) and by nothing else meaningful - an
# access log entry for it is pure noise, never a signal an operator would
# actually want, in the same way most production HTTP access logs exclude
# their own health-check endpoint.
_EXCLUDED_REQUEST_LOG_PATHS = frozenset({"/health"})

# --- Request-scoped context -------------------------------------------------

# One dict per request, holding whatever ambient fields the request-logging
# middleware has populated so far - every logger.*() call made anywhere
# during that request's handling picks these up automatically via
# RequestContextFilter, without needing to pass
# request_id/method/path/client_ip explicitly at each call site. Set once,
# by the middleware itself, which is `async def` and both sets and reads
# these within the same single async context - never mutated afterward by
# a sync dependency, which is precisely what user_id can't do (see
# set_request_user_id below). contextvars, not a plain module-level dict,
# because each request is its own asyncio Task - this is the standard
# mechanism for request-local state in an async framework, and correctly
# isolates concurrent requests from each other's context without any
# locking.
_request_context: ContextVar[dict[str, Any] | None] = ContextVar(
    "medlens_request_context", default=None
)


def get_request_id() -> str | None:
    context = _request_context.get()
    return context.get("request_id") if context else None


def set_request_user_id(request: Request, user_id: int) -> None:
    """Called once by get_current_user (app/api/deps.py) as soon as a
    request's JWT resolves to a real user. Deliberately request.state, not
    the _request_context ContextVar below: get_current_user is a plain
    sync `def`, and Starlette runs every sync dependency/route handler via
    run_in_threadpool, which executes it inside its own *copy* of the
    current context (contextvars.copy_context().run(...)) - a
    ContextVar.set() made there never becomes visible outside that one
    call, not even to the request-logging middleware's own code for the
    same request. request.state is a plain mutable attribute on the one
    Request object every dependency and the middleware all share, so it
    propagates correctly across that boundary. (Verified empirically:
    a ContextVar.set() in one sync dependency is invisible to a sibling
    sync dependency even when both run on the same threadpool-reused OS
    thread; request.state is not.)
    """
    request.state.user_id = user_id


class RequestContextFilter(logging.Filter):
    """Injects the ambient request context onto every LogRecord as it's
    emitted. Applied to the one handler configure_logging installs, so it
    runs for every logger in the process - individual call sites never set
    these fields themselves, only the ones that are specific to that one
    call (event, patient_id, analysis_id, ...) via `extra=`.

    user_id is deliberately NOT one of these fields - see
    set_request_user_id above for why a ContextVar can't carry it reliably
    in this codebase. The request-logging middleware instead reads it from
    request.state and passes it explicitly via extra= for its own summary
    line; any other log call that wants user_id (e.g. auth.py's
    login/register) already has the user object in scope and passes it
    explicitly too.
    """

    _CONTEXT_FIELDS = ("request_id", "method", "path", "client_ip")

    def filter(self, record: logging.LogRecord) -> bool:
        context = _request_context.get() or {}
        for field in self._CONTEXT_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, context.get(field))
        return True


# --- Formatters --------------------------------------------------------------


def _iso_utc(created: float) -> str:
    return (
        datetime.fromtimestamp(created, tz=UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for field in ALLOWED_FIELDS:
        if field == "event":
            continue
        value = getattr(record, field, None)
        if value is not None:
            fields[field] = value
    return fields


class JSONFormatter(logging.Formatter):
    """One JSON object per line - the production format, suited to a log
    aggregator or `docker compose logs` piped through `jq`. Never includes
    a field outside ALLOWED_FIELDS (see above); the exception traceback
    (when present, via logger.exception(...)/exc_info=True) is included as
    a plain string under "exception" - server-side only, never returned to
    an API client (see app/main.py's exception handler).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _iso_utc(record.created),
            "level": record.levelname,
            "logger": record.name,
            "event": getattr(record, "event", None) or record.getMessage(),
            "message": record.getMessage(),
        }
        payload.update(_extra_fields(record))

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """A single readable line per record for local development - the same
    fields JSONFormatter emits, just `key=value` pairs instead of a JSON
    object, since a developer reading a terminal benefits from brevity and
    color-free plain text more than from machine-parseability.
    """

    def format(self, record: logging.LogRecord) -> str:
        event = getattr(record, "event", None) or record.getMessage()
        parts = [
            _iso_utc(record.created),
            f"{record.levelname:8}",
            record.name,
            f"event={event}",
        ]
        for key, value in _extra_fields(record).items():
            parts.append(f"{key}={value}")

        line = " ".join(parts)

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)

        return line


def configure_logging(app_env: str, log_level: str) -> None:
    """The single place formatter/handler setup happens - called once from
    app/main.py, before anything else in the application runs, so even
    early startup issues are logged consistently. Configures the *root*
    logger (not just an "app" namespace), so every `logging.getLogger(__name__)`
    anywhere in this codebase - and any third-party library that logs
    through the standard library - shares the same handler and format
    without needing its own setup.
    """
    formatter: logging.Formatter = (
        ConsoleFormatter() if app_env == "development" else JSONFormatter()
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.addFilter(RequestContextFilter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(log_level.upper())


# --- Request-logging middleware ---------------------------------------------


def configure_request_logging(app: FastAPI) -> None:
    """Registers the one middleware responsible for the "exactly one
    request summary per completed request" requirement. Mirrors
    configure_cors's shape (app/main.py) - a small `configure_x(app, ...)`
    function called once from main.py, the established pattern for wiring
    a cross-cutting FastAPI concern into the app.

    Uvicorn's own default access log is disabled at the process level (see
    the Dockerfile's CMD and docs/deployment.md) specifically so this is
    the *only* per-request log line, not a second one in a different
    format alongside it.
    """

    @app.middleware("http")
    async def _log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _EXCLUDED_REQUEST_LOG_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())
        started_at = time.monotonic()
        token = _request_context.set(
            {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None,
            }
        )

        try:
            try:
                response = await call_next(request)
            except Exception:
                # Defensive: FastAPI's own registered exception handler
                # (configure_exception_handling, app/main.py) is what
                # normally turns an unhandled exception into a Response
                # *before* it ever reaches this middleware, so this branch
                # only fires for something that bypasses that entirely
                # (e.g. a failure in another middleware). Logged here too
                # so "log full exception details on the server" holds even
                # in that edge case, then re-raised unchanged - this
                # middleware never decides how a crash is turned into a
                # response, only observes and logs it.
                duration_ms = (time.monotonic() - started_at) * 1000
                logger.exception(
                    "Unhandled exception while processing request",
                    extra={
                        "event": "http_request_failed",
                        "duration_ms": round(duration_ms, 1),
                        "user_id": getattr(request.state, "user_id", None),
                    },
                )
                raise

            duration_ms = (time.monotonic() - started_at) * 1000
            logger.info(
                "Request completed",
                extra={
                    "event": "http_request_completed",
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 1),
                    # Read from request.state, not the ambient context - see
                    # set_request_user_id's docstring above for why user_id
                    # specifically can't ride the _request_context ContextVar
                    # the way request_id/method/path/client_ip do.
                    "user_id": getattr(request.state, "user_id", None),
                },
            )
            response.headers["X-Request-ID"] = request_id

            return response
        finally:
            # Reset only after both logging branches above have already
            # run within this context - resetting first would mean the
            # request-summary log itself is missing request_id/method/path,
            # defeating the point of the log line it's attached to.
            _request_context.reset(token)


# --- Global exception handling -----------------------------------------------


def configure_exception_handling(app: FastAPI) -> None:
    """Registers a handler for the bare `Exception` type only - FastAPI
    already has its own, higher-priority handler for `HTTPException`
    (registered by FastAPI itself, unrelated to this function), so every
    existing `raise HTTPException(...)` throughout this app (401s, 404s,
    409s, 422s, 503s, ...) is completely unaffected and keeps producing
    exactly the response it already did. This handler only ever fires for
    a genuinely unexpected exception - a bug, not a deliberate application
    response - which is exactly the "unhandled exceptions" this issue asks
    to log.
    """

    @app.exception_handler(Exception)
    async def _handle_unhandled_exception(request: Request, exc: Exception) -> Response:
        # Full traceback via exc_info=True - server-side only. The
        # response below never includes the exception's message or type,
        # so a client learns nothing beyond "something went wrong" - see
        # this issue's own "Do not expose stack traces or sensitive
        # information to API clients" requirement.
        logger.error(
            "Unhandled exception",
            exc_info=exc,
            extra={"event": "unhandled_exception"},
        )

        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
