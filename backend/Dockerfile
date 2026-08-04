# Build stage: installs dependencies in isolation so the final image never
# carries pip's build cache, wheel metadata, or anything else the install
# process leaves behind - only the installed packages themselves.
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .

# --prefix, not --user: --user ties the install to root's home directory
# (/root/.local), which the non-root runtime user below can't read.
# --prefix installs to a plain directory that gets copied wholesale into
# the final stage's /usr/local, already on PATH and Python's search path
# for any user.
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Runtime stage: a fresh base with nothing but the installed dependencies
# and application code - no pip, no build artifacts.
FROM python:3.12-slim

# Runs as a dedicated non-root user rather than the image's default root -
# the application never needs root privileges, and this stage is the only
# one that matters at runtime, so cutting root access here doesn't affect
# how dependencies were installed above.
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

COPY --from=builder /install /usr/local
COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000

# Applies any pending Alembic migrations before the server starts - without
# this, a fresh database (a brand-new deployment, or a first `docker
# compose up` on a clean volume) has no tables at all, and every
# database-touching request fails. Safe to run on every container start:
# `alembic upgrade head` against an already-current database is a no-op.
# See alembic/env.py for how this resolves DATABASE_URL correctly whether
# running here (Postgres reachable by its compose service name) or
# directly on a developer's host (Postgres reachable at localhost).
#
# --no-access-log (Issue #59): the application's own request-logging
# middleware (app/core/logging_config.py) already logs exactly one
# structured summary line per completed request - uvicorn's default access
# log would otherwise add a second, differently-formatted line for the
# same request, right alongside it.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log"]
