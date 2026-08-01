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

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
