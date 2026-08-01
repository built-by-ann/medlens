# Deployment

## Overview

MedLens is designed to be deployed as a Dockerized full-stack web application on AWS. The deployment architecture emphasizes reproducibility, scalability, and production-style engineering practices while remaining simple enough for a single-developer project.

The application will initially be deployed to a single AWS EC2 instance using Docker Compose, with optional future improvements such as managed databases, reverse proxies, and container orchestration.

---

## Deployment Architecture

The planned production environment consists of:

- React frontend
- FastAPI backend
- PostgreSQL database
- Docker containers
- AWS EC2
- AWS S3 (for uploaded files)

```text
                 Internet
                     │
                     ▼
              AWS EC2 Instance
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Frontend     FastAPI      PostgreSQL
    Container    Container     Container
                     │
                     ▼
                Gemini API

(Optional)

FastAPI ─────────────► AWS S3
```

---

## Local Development

Local development uses Docker Compose (`infra/docker-compose.yml`) to ensure every service can be started consistently.

Containers:

- `frontend` - the production image (Vite build served by nginx, see Docker Image Builds below), added in Issue #56. Local frontend *development* still uses `npm run dev` (see the root `README.md`), which hot-reloads and doesn't require Docker at all; this container exists to validate and run the deployable image, not to replace that faster loop.
- `backend`
- `postgres`

The application is runnable with:

```bash
cd infra
docker compose up --build
```

| Service | Host port | Container port |
|---|---|---|
| `frontend` | `8080` | `80` (nginx) |
| `backend` | `8000` | `8000` |
| `postgres` | `5432` | `5432` |

`docker compose down` stops and removes the containers and network; add `-v` to also remove the named Postgres volume (`medlens_postgres_data`) and start from an empty database next time.

---

## Production Environment

The initial production deployment will include:

- Dockerized frontend
- Dockerized backend
- PostgreSQL
- Environment variables
- Persistent database storage
- Structured application logs

Future versions may include:

- Nginx reverse proxy
- HTTPS
- Load balancing
- Managed PostgreSQL (AWS RDS)

---

## Environment Variables

Configuration values will be managed through environment variables.

Examples include:

- DATABASE_URL
- JWT_SECRET_KEY
- GEMINI_API_KEY
- CORS_ALLOWED_ORIGINS
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION
- S3_BUCKET_NAME

Sensitive values will never be committed to the repository.

An `.env.example` file will document required variables.

See Docker Image Builds below for `VITE_API_BASE_URL`, `DATABASE_URL`, `JWT_SECRET_KEY`, `GEMINI_API_KEY`, and `CORS_ALLOWED_ORIGINS` as they apply specifically to building and running the Docker images - including the one variable that's a *build* argument rather than a runtime one.

---

## Docker Strategy

Each major component has its own Dockerfile:

- `backend/Dockerfile` - multi-stage: a `builder` stage installs Python dependencies with pip, a slim runtime stage copies only the installed packages and application code, and runs as a dedicated non-root user.
- `frontend/Dockerfile` - multi-stage: a Node `builder` stage runs the same `npm ci && npm run build` CI already runs, an `nginx:alpine` runtime stage serves the resulting static files, with an SPA fallback route (`frontend/nginx.conf`) so client-side routes survive a direct load or refresh.
- `postgres` uses the stock `postgres:16` image directly - no Dockerfile of its own.

Docker Compose (`infra/docker-compose.yml`) coordinates all three for local development. See Docker Image Builds below for build commands, environment variables, and the full set of decisions behind both Dockerfiles.

---

## Continuous Integration

- `.github/workflows/frontend.yml` (Issue #55) runs on every push and pull request to `main`/`develop` that touches the frontend: `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm test`, and `npm run build`, in that order, on `ubuntu-latest` with Node 20. See `docs/frontend.md`'s "Continuous Integration" section for the full breakdown.
- `.github/workflows/backend.yml` (Issue #54) runs the same way for the backend: `ruff format --check .`, `ruff check .`, and `pytest -v`, against a `postgres:16` service container, on `ubuntu-latest` with Python 3.12. See `docs/testing.md`'s "Continuous Integration" section for the full breakdown, including why `GEMINI_API_KEY` is deliberately left unset.

**Docker image builds (Issue #56)** are the final step of each workflow above, not a third workflow - `docker build` for the matching Dockerfile, after every existing check has already passed. See Docker Image Builds below.

---

## Docker Image Builds (Issue #56)

Issue #56's goal was narrow and deliberately stops short of deployment: prove the production Docker images always build, both locally and in CI, before they're ever relied on for a real deploy. It does not deploy anything to AWS, does not add monitoring, and does not change how the application behaves - only whether its two deployable images (and the frontend one's existence at all - see below) can be trusted to build.

### What was missing before this issue

Auditing the existing Docker setup against this issue's own checklist turned up more gaps than expected:

- **`frontend/Dockerfile` didn't exist.** Only `backend/Dockerfile` did. `infra/docker-compose.yml` had no `frontend` service either - "planned containers: frontend, backend, postgres" was still true only in this document, not in the actual compose file. Both are added by this issue (below), since "frontend image builds successfully" and "docker compose up starts every service successfully" can't be verified against something that doesn't exist.
- **Neither Dockerfile had a matching `.dockerignore`.** `backend/Dockerfile`'s `COPY . .` had nothing excluding it from the build context, which meant a real `docker build` would have copied `backend/.env` (a developer's actual local secrets - `DATABASE_URL`, `JWT_SECRET_KEY`, `GEMINI_API_KEY`) directly into an image layer, along with `.venv` (182 MB) and `.pytest_cache`/`.ruff_cache`. The same was true on the frontend side for `.env` and `node_modules` (196 MB), once `frontend/Dockerfile` existed to have a context at all. Both now have a `.dockerignore` (see Design Decisions below).
- **`infra/docker-compose.yml`'s `backend` service was missing `JWT_SECRET_KEY`.** `Settings()` (`app/core/config.py`) requires it with no default; the only reason `docker compose up` previously "worked" is that the missing `.dockerignore` let a developer's local `backend/.env` leak into the image, which `pydantic-settings`' `env_file=".env"` then read from disk inside the container. Fixing the `.dockerignore` leak (correctly) broke that accidental path, so the compose file now sets it directly, the same way `backend.yml`'s CI job already does, with the same non-secret placeholder reasoning.

None of this was a redesign - every fix above is either a missing file this issue's own checklist explicitly asks to review (`.dockerignore`, `frontend/Dockerfile`) or a value the application already required and was silently getting from an unsafe source.

### Building the images locally

```bash
# Backend
cd backend
docker build -t medlens-backend .

# Frontend (VITE_API_BASE_URL defaults to http://localhost:8000 if omitted -
# see Environment Variables below)
cd frontend
docker build -t medlens-frontend .

# Both, plus postgres, via Compose
cd infra
docker compose build
docker compose up --build
docker compose down       # add -v to also drop the postgres volume
```

A clean rebuild (`docker build --no-cache`) was verified to succeed for both images - the build only depends on `requirements.txt`/`package-lock.json` and the application source, never on a previous build's cache being present.

### Environment Variables

| Variable | Where it's needed | Required | Notes |
|---|---|---|---|
| `VITE_API_BASE_URL` | Frontend **image build** (`docker build --build-arg`) | No - defaults to `http://localhost:8000` | Vite inlines `import.meta.env.VITE_API_BASE_URL` into the built JS bundle at build time, not at container start - unlike a typical server-side app, this can't be changed by restarting the container with a different environment variable. A real deployment overrides it: `docker build --build-arg VITE_API_BASE_URL=https://api.example.com .` |
| `DATABASE_URL` | Backend **container runtime** | Yes | `infra/docker-compose.yml` sets it to the `postgres` service's in-network address. |
| `JWT_SECRET_KEY` | Backend **container runtime** | Yes | `infra/docker-compose.yml` sets a placeholder value - see "What was missing before this issue" above. A real deployment must override this with a real secret, e.g. via a platform's own secret store, not a value committed anywhere. |
| `GEMINI_API_KEY` | Backend **container runtime** | No | AI features return a `503` with a clear error when unset (see `docs/api.md`) rather than the container failing to start. |
| `CORS_ALLOWED_ORIGINS` | Backend **container runtime** | No | Defaults to empty; see `.env.example`. |

The distinction in the first row - a frontend *build* argument versus a backend *runtime* environment variable - is the one genuinely non-obvious piece of configuration this issue's Dockerfiles have to get right, and is why `frontend/Dockerfile`'s `ARG`/`ENV` pair and `frontend.yml`'s `--build-arg` flag exist at all (see `docs/frontend.md`'s Continuous Integration section).

### Verifying CI without pushing a commit

`.github/workflows/backend.yml` and `.github/workflows/frontend.yml` were both checked with [`actionlint`](https://github.com/rhysd/actionlint) (`actionlint .github/workflows/*.yml`), which validates GitHub Actions workflow syntax and semantics beyond plain YAML parsing (unknown keys, bad expression syntax, shell-script issues inside `run:` steps via its bundled `shellcheck`) - both files pass with no findings.

### Design decisions

See `docs/design-decisions.md` (Decision 18) for the full reasoning behind each Dockerfile's shape: multi-stage builds, running the backend as a non-root user, why `frontend/Dockerfile` serves the build with nginx rather than `npm run preview` or a Node static-file server, and why `.dockerignore` was treated as a security fix rather than a cleanup nice-to-have.

---

## Continuous Deployment

The planned deployment workflow is:

1. Push changes to a feature branch.
2. Open a pull request.
3. Run automated tests.
4. Merge into `develop`.
5. Merge release into `main`.
6. Build Docker images.
7. Deploy the latest version to AWS EC2.

---

## Monitoring

The deployed application will include basic observability features such as:

- Health endpoint
- Request logging
- Error logging
- Processing time metrics
- Database connectivity checks

Future improvements may include:

- AWS CloudWatch
- Sentry
- Performance dashboards

---

## Future Improvements

Potential production improvements include:

- AWS RDS
- Redis
- Celery background workers
- Nginx reverse proxy
- HTTPS certificates
- Kubernetes
- Auto-scaling
- Blue-green deployments
- Custom domain

---

## Deployment Goals

The deployment strategy is intended to demonstrate production engineering practices, including:

- Containerized development
- Cloud deployment
- Infrastructure as code
- Automated testing
- Continuous integration
- Secure configuration management
- Scalable application architecture

---

## Status

This document outlines the intended deployment strategy and will evolve as deployment infrastructure is implemented throughout the project.