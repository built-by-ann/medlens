# syntax=docker/dockerfile:1
# Pins the BuildKit Dockerfile frontend version so `--mount=type=cache`
# below (Issue #184) is recognized consistently regardless of the exact
# Docker Engine version running this build (local, CI, or a future EC2
# instance) - the syntax pragma, not the Engine version, is what selects
# the frontend that understands cache mounts.

# Build stage: installs dependencies in isolation so the final image never
# carries pip's build cache, wheel metadata, or anything else the install
# process leaves behind - only the installed packages themselves (pip's
# own cache lives in a BuildKit mount below, not this layer, either way).
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .

# --prefix, not --user: --user ties the install to root's home directory
# (/root/.local), which the non-root runtime user below can't read.
# --prefix installs to a plain directory that gets copied wholesale into
# the final stage's /usr/local, already on PATH and Python's search path
# for any user.
#
# --mount=type=cache (Issue #184), not --no-cache-dir: a cache *mount* is
# never included in the exported image layer at all (unlike pip's normal
# on-disk cache directory would be), so it gets the same "no cache bloat
# in the final image" property --no-cache-dir was originally chosen for
# (Decision 18) - but unlike --no-cache-dir, this cache persists *between*
# builds (BuildKit's own cache store, separate from image layers
# entirely), so a build that only adds one line to requirements.txt
# reuses every already-downloaded wheel instead of redownloading all of
# them from PyPI. Measured locally: a requirements.txt change with a warm
# mount installs every package from "Using cached ..." wheels, zero
# network requests - see this issue's final report for the full numbers.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt

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
#
# --forwarded-allow-ips='*' (Issue #190): every request now arrives via
# the frontend container's nginx reverse proxy (frontend/nginx.conf),
# never directly from a browser - uvicorn's X-Forwarded-For/-Proto support
# is already on by default, but it only trusts those headers from
# 127.0.0.1 unless told otherwise, and nginx's requests arrive from its
# own Docker-network address, not 127.0.0.1. Trusting every source here is
# safe specifically because this port is no longer published beyond
# 127.0.0.1 on the host (infra/docker-compose.yml) - nginx is the only
# thing that can reach this container at all in a real deployment.
# Without this, every request's client_ip (app/core/logging_config.py)
# would log nginx's own container address instead of the real visitor.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log --forwarded-allow-ips='*'"]
