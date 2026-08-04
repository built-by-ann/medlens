# Deployment

## Overview

MedLens is deployed as a Dockerized full-stack web application on AWS. The deployment emphasizes reproducibility and simplicity appropriate to a single-developer project over scalability - one EC2 instance, running the same three containers (`frontend`, `backend`, `postgres`) locally validated in Issue #56, coordinated by the same Docker Compose file used for local development.

Issue #56 validated that the production images build, both locally and in CI. Issue #57 (this document's "AWS EC2 Deployment" section, below) is what actually runs them on a real EC2 instance. HTTPS, a custom domain, a reverse proxy, managed databases, and container orchestration (ECS/EKS/Kubernetes) are all explicitly deferred - see that section's Production Readiness subsection for the full list and why each is deferred rather than overlooked.

---

## Deployment Architecture

The current production environment consists of:

- React frontend (served as a static build by nginx - see Docker Strategy below)
- FastAPI backend
- PostgreSQL database
- Docker containers, coordinated by Docker Compose
- A single AWS EC2 instance

See the "AWS EC2 Deployment" section below for the full architecture diagram, the deployment runbook, and why there's no reverse proxy or S3 integration - neither exists in this application today (uploaded documents are stored as extracted text in Postgres, never as files on disk or in object storage - see `docs/data-model.md`), so nothing here depends on either.

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

The current production deployment (see "AWS EC2 Deployment" below for the full runbook) includes:

- Dockerized frontend (nginx serving a static build) and backend, each with a Docker-level health check and `restart: unless-stopped`
- PostgreSQL, with its data on a named Docker volume that survives container restarts and `docker compose down` (without `-v`)
- Configuration and secrets via environment variables (`infra/.env`, gitignored - never a value hardcoded in a tracked file)
- Database migrations applied automatically on every backend container start
- Application logs via `docker compose logs` (plain container stdout/stderr - no structured/shipped logging yet, see Production Readiness below)

Deferred to a future iteration, in explicit scope per Issue #57's own instructions - see "AWS EC2 Deployment" below's Production Readiness subsection for the full reasoning behind each:

- Nginx (or similar) reverse proxy in front of both application containers
- HTTPS / TLS
- DNS / a custom domain
- Load balancing / multiple instances
- Managed PostgreSQL (AWS RDS)
- Automated (CI-triggered) deployment
- Monitoring, alerting, and backups

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
| `DATABASE_URL` | Backend **container runtime** | Yes | `infra/docker-compose.yml` builds this from `POSTGRES_PASSWORD` below and the `postgres` service's in-network address - set `POSTGRES_PASSWORD`, not `DATABASE_URL` itself, when using Compose. |
| `JWT_SECRET_KEY` | Backend **container runtime** | Yes | `infra/docker-compose.yml` defaults to a placeholder value - see "What was missing before this issue" above. **Issue #57's AWS EC2 Deployment section below covers overriding this (and every variable in this table) via `infra/.env` for a real deployment** - never edit `docker-compose.yml` itself to set a real secret. |
| `GEMINI_API_KEY` | Backend **container runtime** | No | AI features return a `503` with a clear error when unset (see `docs/api.md`) rather than the container failing to start. |
| `GEMINI_MODEL` | Backend **container runtime** | No - defaults to `gemini-2.5-flash` | Which Gemini model to call - see `docs/ai.md`'s "A Note on Model Retirement." Changing this only needs `infra/.env` updated and the backend container restarted (`docker compose up -d backend`), never a rebuild - useful when Google retires the current default, which has already happened once (`gemini-2.0-flash`, fixed by changing this same default). |
| `CORS_ALLOWED_ORIGINS` | Backend **container runtime** | No, but required in practice once `APP_ENV=production` | Defaults to empty; see `.env.example`. Comma-separated frontend origin(s), e.g. `http://<ec2-public-ip>:8080`. |
| `APP_ENV` (Issue #57) | Backend **container runtime** | No - defaults to `development` | `development` auto-allows any `localhost`/`127.0.0.1` origin for CORS in addition to `CORS_ALLOWED_ORIGINS` (see `app/main.py`) - correct for local Docker use, wrong for a real deployment, which should set this to `production`. |
| `POSTGRES_PASSWORD` (Issue #57) | Backend + `postgres` **container runtime** | No - defaults to `medlens_password` | `infra/docker-compose.yml` references this one variable in both the `postgres` service's own credentials and the backend's `DATABASE_URL`, so they can't drift out of sync. Change it before any real deployment. |
| `FRONTEND_PORT` / `BACKEND_PORT` (Issue #57) | Host, at `docker compose up` time | No - default to `8080`/`8000` | Which host ports Compose publishes the containers on - not read by the application itself. Set `FRONTEND_PORT=80` for a deployment reachable at `http://<ec2-public-ip>/` with no port suffix. |
| `STORAGE_BACKEND` (Issue #58) | Backend **container runtime** | No - defaults to `local` | `local` or `s3` - see the "File Storage (S3)" section below for the full setup. |
| `AWS_REGION` / `S3_BUCKET_NAME` (Issue #58) | Backend **container runtime** | Only when `STORAGE_BACKEND=s3` | The backend fails to start with a clear error if either is missing while `s3` is selected - see "File Storage (S3)" below. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` (Issue #58) | Backend **container runtime** | No | Leave unset in production - an IAM role attached to the EC2 instance is used instead. Only set for local development against a real bucket. See "File Storage (S3)" below. |

The distinction in the first row - a frontend *build* argument versus every other variable being a *runtime* one - is the one genuinely non-obvious piece of configuration to get right, and is why `frontend/Dockerfile`'s `ARG`/`ENV` pair and `frontend.yml`'s `--build-arg` flag exist at all (see `docs/frontend.md`'s Continuous Integration section).

### Verifying CI without pushing a commit

`.github/workflows/backend.yml` and `.github/workflows/frontend.yml` were both checked with [`actionlint`](https://github.com/rhysd/actionlint) (`actionlint .github/workflows/*.yml`), which validates GitHub Actions workflow syntax and semantics beyond plain YAML parsing (unknown keys, bad expression syntax, shell-script issues inside `run:` steps via its bundled `shellcheck`) - both files pass with no findings.

### Design decisions

See `docs/design-decisions.md` (Decision 18) for the full reasoning behind each Dockerfile's shape: multi-stage builds, running the backend as a non-root user, why `frontend/Dockerfile` serves the build with nginx rather than `npm run preview` or a Node static-file server, and why `.dockerignore` was treated as a security fix rather than a cleanup nice-to-have.

---

## AWS EC2 Deployment (Issue #57)

Where Issue #56 stopped at "the images build," this issue is "the images run, in production, on a real EC2 instance, using Docker Compose" - reusing exactly those images and `infra/docker-compose.yml`, not a redesign. Deliberately out of scope, per the issue itself, and covered instead under Production Readiness below as intentionally deferred work: DNS, HTTPS/TLS, a reverse proxy, ECS/EKS/Kubernetes, and automated (CI-triggered) deployment. This is a single EC2 instance, reached directly by IP and port, updated by hand over SSH.

### Deployment architecture

```text
                        Internet
                            │
              ┌─────────────┼─────────────┐
              │ security group             │
              │ 22 (SSH)   8080  8000      │
              └─────┬────────┬───────┬─────┘
                    ▼        ▼       ▼
              ┌─────────────────────────────────┐
              │         EC2 instance             │
              │                                   │
              │  frontend container (nginx) :8080 │
              │  backend container (uvicorn) :8000│
              │  postgres container :5432          │
              │    (127.0.0.1 only - not exposed  │
              │     through the security group)   │
              │                                   │
              │  docker compose (infra/)          │
              └───────────────┬───────────────────┘
                              ▼
                         Gemini API
```

No reverse proxy sits in front of the two application containers - the frontend and backend are each reached directly on their own published port, exactly as `infra/docker-compose.yml` already publishes them for local use (see Local Development above). This is the same architecture, unchanged, just running on an EC2 instance instead of a laptop.

### Prerequisites

- An AWS account with permission to launch an EC2 instance and edit its security group.
- An SSH key pair (create one in the EC2 console, or import an existing public key) - needed to reach the instance at all.
- A Gemini API key, if AI features should work (optional - see the Environment Variables table above).

### Step 1: Launch an EC2 instance

1. EC2 console → **Launch instance**.
2. **AMI**: Ubuntu Server 22.04 LTS (or 24.04 LTS) - these instructions assume Ubuntu's `apt`-based install; Amazon Linux 2023 works too but uses `dnf` and a different Docker install path.
3. **Instance type**: `t3.small` (2 GiB RAM) is the practical minimum - building the frontend image (`npm ci && vite build`, see `docs/deployment.md`'s Docker Image Builds section) is memory-hungry enough that `t3.micro`'s 1 GiB can OOM mid-build. `t3.medium` gives more headroom if the free tier doesn't matter.
4. **Key pair**: select the one from Prerequisites.
5. **Storage**: the default 8 GiB gp3 root volume is tight once Docker's image layers and build cache accumulate - 20 GiB avoids babysitting disk space.
6. **Security group**: create a new one now; configure it in the next step before launching, not after.

### Step 2: Configure the security group

See Security below for the reasoning; the rules themselves:

| Type | Port | Source | Purpose |
|---|---|---|---|
| SSH | 22 | Your own IP only (`My IP` in the console) | Administration. Never `0.0.0.0/0` - an SSH port open to the entire internet is scanned and attacked continuously. |
| Custom TCP | 8080 (or `FRONTEND_PORT`, see below) | `0.0.0.0/0` | The web app itself. |
| Custom TCP | 8000 (or `BACKEND_PORT`) | `0.0.0.0/0` | The API - the browser calls this directly (see Deployment Architecture above; there's no reverse proxy to hide it behind). |

**5432 (Postgres) is deliberately absent from this table** - `infra/docker-compose.yml` binds it to `127.0.0.1` only (see Docker Strategy above), so it isn't reachable from outside the instance even if a security group rule mistakenly allowed it. Nothing to configure here; this is enforced at the Docker level, not the AWS level, on purpose - see Security below.

### Step 3: Install Docker and Docker Compose

SSH in, then run Docker's official convenience script (installs the Docker Engine, CLI, and the `docker compose` plugin together - this is genuinely the `docker compose` used throughout this document, not the older standalone `docker-compose` Python tool):

```bash
ssh -i /path/to/your-key.pem ubuntu@<ec2-public-ip>

curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

Log out and back in (`exit`, then SSH in again) for the group change to take effect - without it, every `docker` command below needs `sudo` in front of it. Confirm both are present:

```bash
docker --version
docker compose version
```

### Step 4: Clone the repository

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/built-by-ann/medlens.git
cd medlens/infra
```

### Step 5: Configure environment variables

```bash
cp .env.example .env
nano .env      # or vim, or any editor
```

Fill in, at minimum, `JWT_SECRET_KEY` and `POSTGRES_PASSWORD` (both required for a real deployment - see Security below), and `VITE_API_BASE_URL` (set it to `http://<ec2-public-ip>:8000`, using this instance's actual public IP - the frontend image bakes this in at build time in the next step, so it must be correct *before* building, not after). Set `APP_ENV=production` and `CORS_ALLOWED_ORIGINS=http://<ec2-public-ip>:8080` (or whatever `FRONTEND_PORT` is set to) so the deployed frontend's origin is actually allowed to call the API. `infra/.env` is gitignored - it never gets committed, by this repository's own `.gitignore`, regardless of what's in it.

### Step 6: Build the images

```bash
docker compose build
```

This is the exact `docker build` already validated in CI (Issue #56) for each image, run here against `infra/.env`'s real values instead of CI's/local dev's placeholders - `VITE_API_BASE_URL` is what actually gets baked into the frontend bundle this time.

### Step 7: Start the application

```bash
docker compose up -d
```

`-d` (detached) so the application keeps running after the SSH session ends - without it, closing the terminal stops every container. `restart: unless-stopped` on all three services (see Production Configuration below) means they also come back automatically if the instance itself reboots, with no manual step needed.

### Verifying the deployment

```bash
# From the instance itself:
docker compose ps                     # all three services should show "healthy" within ~30s
curl http://localhost:8000/health     # {"status":"ok","database":"connected"}

# From your own machine:
curl http://<ec2-public-ip>:8000/health
```

Then open `http://<ec2-public-ip>:8080` in a browser - the app should load, and registering an account should succeed (this exercises the database end to end, proving migrations actually ran - see Production Configuration below for why that specifically used to be broken).

### Updating the application

```bash
cd ~/medlens
git pull
cd infra
docker compose build
docker compose up -d
```

`docker compose up -d` after a rebuild only recreates containers whose image actually changed - if just the backend changed, the frontend and postgres containers aren't touched (and keep running, with no downtime for them). Migrations run automatically as each backend container starts (see Production Configuration below), so a schema change ships as part of this same `git pull` + rebuild, with no separate migration step to remember.

### Rollback procedure

There's no automated rollback (out of scope - see Production Readiness below), but the manual version is a normal `git` operation followed by the same update steps:

```bash
cd ~/medlens
git log --oneline -10       # find the last known-good commit
git checkout <commit-sha>   # or: git checkout <previous-tag>
cd infra
docker compose build
docker compose up -d
```

**A rollback that crosses a database migration is the one case this doesn't handle for you.** Rolling the application code back to before a migration was added does not reverse that migration - the schema stays at whatever it was upgraded to. This is a real limitation, not an oversight: `alembic downgrade` exists and can reverse a specific migration by hand if truly needed, but running it against a production database is exactly risky enough that it shouldn't happen as an unattended part of a generic rollback command. If a deployed migration needs to be reversed, do it deliberately, one migration at a time, and back up the volume first (see Production Readiness below).

### Viewing logs

```bash
docker compose logs                    # every service, most recent first
docker compose logs -f                 # follow in real time (Ctrl+C to stop)
docker compose logs backend            # one service only
docker compose logs --tail 100 backend # last 100 lines, then exit
```

### Stopping and restarting services

```bash
docker compose stop                # stop containers, keep them (and the network/volume) around
docker compose start               # start them again, unchanged
docker compose restart             # stop + start in one step
docker compose restart backend     # just one service

docker compose down                # stop AND remove containers + network (the postgres volume survives)
docker compose down -v             # also remove the postgres volume - genuinely destroys all data, only for
                                    # a real reset, e.g. rebuilding the whole environment from scratch
```

### Troubleshooting

- **A container shows `unhealthy` or keeps restarting.** `docker compose ps` shows which one; `docker compose logs <service>` almost always explains why. A backend stuck unhealthy immediately after a fresh `docker compose up` is most often `postgres` not being reachable yet - `depends_on: condition: service_healthy` (see Production Configuration below) should prevent this by making backend wait, but if `postgres` itself never reports healthy, check its own logs first.
- **`docker compose build` fails partway through, out of memory.** Most common on `t3.micro` - the frontend build (`npm ci && vite build`) is the usual culprit. Either resize the instance (Step 1) or add swap: `sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`.
- **The frontend loads but every request fails with a CORS error in the browser console.** `CORS_ALLOWED_ORIGINS` doesn't include the frontend's real origin, or `APP_ENV` is still `development` was assumed instead of set - see Step 5 and `app/main.py`'s `configure_cors`. Fix `infra/.env`, then `docker compose up -d` (no rebuild needed - these are runtime environment variables, not baked in).
- **The frontend loads but API calls go to the wrong place / `localhost`.** `VITE_API_BASE_URL` was wrong (or left at its default) when the frontend image was built. Fix `infra/.env` and **rebuild** (`docker compose build frontend`) - restarting the container alone does nothing, since this value is baked into the JS bundle at build time (see Environment Variables above).
- **`docker: permission denied` on every command.** The `usermod -aG docker` group change from Step 3 needs a fresh login to take effect - log out and back in (or run `newgrp docker` in the current shell as a one-session workaround).
- **Registering a user (or any database write) fails with a 500.** Almost certainly a missed migration - check `docker compose logs backend` for `alembic` output near the top of the log; a real error there (not just the normal "Running upgrade..." lines) means the schema didn't apply. This should be automatic on every backend start (see Production Configuration below), so a persistent failure here is worth investigating directly rather than working around.
- **Creating an analysis always fails with a 503, "Gemini request failed: ClientError."** Check `docker compose logs backend` for the accompanying `detail=` field (see `docs/ai.md`'s Logging section) - `"models/<name> is not found"` means Google has retired the configured model server-side, exactly what happened to `gemini-2.0-flash` in production. Fix: set `GEMINI_MODEL` in `infra/.env` to a current model name and restart the backend (`docker compose up -d backend`) - no rebuild needed, this is a runtime variable (see Environment Variables above).

### Production Configuration Changes (Issue #57)

Auditing the setup this issue inherited from Issue #56 against a real deployment (not just "does `docker build` succeed") found three gaps that would have made a genuine EC2 deployment either broken or insecure. Fixing them is the entire change to `infra/docker-compose.yml`, `backend/Dockerfile`, and `backend/alembic/env.py`:

- **Nothing ever ran database migrations.** `alembic.ini`'s `sqlalchemy.url` is a hardcoded `localhost:5432` connection string, correct only when `alembic` runs directly on a developer's host. Verifying this issue's deployment against a genuinely fresh database (see Manual Verification in the final report) hit `relation "users" does not exist` on the very first `/auth/register` call - the schema was simply never created. Fixed two ways together: `backend/alembic/env.py` now prefers `DATABASE_URL` from the environment over `alembic.ini`'s static value (so migrations resolve the right host whether run inside a container or on a developer's machine), and `backend/Dockerfile`'s `CMD` now runs `alembic upgrade head` before starting `uvicorn` on every container start - a no-op against an already-current database, so this is safe on every restart, not just the first one. See `docs/design-decisions.md` (Decision 19).
- **`JWT_SECRET_KEY` (and every other backend secret) was a value hardcoded directly in `docker-compose.yml`.** Fine for local development and CI (Issue #56's own reasoning - nothing there is a real secret), but a literal value committed in a tracked YAML file is by definition not something a real deployment can keep secret. `infra/docker-compose.yml` now reads `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `GEMINI_API_KEY`, `APP_ENV`, and `CORS_ALLOWED_ORIGINS` via `${VAR:-default}` substitution from `infra/.env` (new, gitignored, git-ignored the same way `backend/.env`/`frontend/.env` already are - see Security below), each still defaulting to the exact placeholder Issue #56 used, so local development and CI need no changes at all.
- **Postgres's port was published to every network interface.** `- "5432:5432"` in Docker Compose binds to `0.0.0.0` by default - reachable from outside the host if a security group ever allowed it, which is one misconfiguration away from a public database. Changed to `- "127.0.0.1:5432:5432"` - still reachable from the host itself (`psql -h localhost`, an SSH tunnel), never from outside it, regardless of the security group. See Security below.

Also added, for the reliability this issue's own task list asks for: `restart: unless-stopped` on all three services (so a container that crashes, or an instance that reboots, recovers without a manual `docker compose up`), and Docker-level `healthcheck`s for all three (`postgres`: `pg_isready`; `backend`: an HTTP check that parses `/health`'s response body rather than trusting its always-200 status code, since the endpoint itself can report `"database": "disconnected"` with a 200 - see `docs/api.md`; `frontend`: a plain `wget --spider` against nginx). `backend` now declares `depends_on: postgres: condition: service_healthy` instead of the previous unconditional `depends_on: - postgres`, which only ever waited for the postgres *container* to start, not for Postgres itself to be ready to accept connections - closing exactly the transient "database disconnected" race Issue #56's own final report flagged as a known limitation.

### Security

- **Containers run as non-root where applicable.** The backend runs as a dedicated `appuser` (Issue #56, `backend/Dockerfile`) - verified again for this issue (`docker exec <container> whoami` → `appuser`). The frontend's `nginx:alpine` runtime uses the standard nginx image as-is: its master process binds port 80 as root (required to bind a port below 1024) and hands actual request handling off to worker processes running as the unprivileged `nginx` user, nginx's own well-established privilege-separation model - not something this project's Dockerfile needs to (or should) override. `postgres:16` is the stock upstream image, whose own entrypoint already drops to a non-root `postgres` user.
- **Secrets are never committed.** `infra/.env` (real values) is covered by the repository's existing blanket `.env` rule in `.gitignore` (confirmed with `git check-ignore -v infra/.env`) - the same rule that already covers `backend/.env`/`frontend/.env`. Only `infra/.env.example` (placeholders, no real values - the same pattern as `backend/.env.example`/`frontend/.env.example`) is tracked.
- **`.env` usage is documented** in Step 5 above and inline in `infra/.env.example` itself - every variable there has a comment explaining what it's for and, where it matters, whether changing it requires a rebuild (`VITE_API_BASE_URL`) or just a restart (everything else).
- **Security group configuration** is Step 2 above; summarized:

  | Port | Exposed to | Why |
  |---|---|---|
  | 22 (SSH) | Your IP only | Administration access. |
  | 8080 (frontend, or `FRONTEND_PORT`) | Everyone | The application. |
  | 8000 (backend, or `BACKEND_PORT`) | Everyone | The API - called directly by the browser, since there's no reverse proxy in front of it (see Deployment Architecture above). |
  | 5432 (Postgres) | **Nobody** | Bound to `127.0.0.1` inside `docker-compose.yml` itself (see Production Configuration Changes above) - there is no security group rule that could expose it even by mistake, since the port is never listening on a network interface a security group rule could apply to in the first place. |

### Production Readiness

**Reproducibility**: verified directly, not assumed - a fresh copy of this repository (simulating a clean `git clone`, no local Docker cache or state reused) built and ran successfully with zero configuration (every default in `infra/docker-compose.yml` kicking in), and separately with a real `infra/.env` overriding every secret, matching exactly what Step 5 above asks a real deployment to do. See Manual Verification in the final report for the full sequence.

**Reliability**: `restart: unless-stopped` and the three healthchecks (Production Configuration Changes above) mean the stack recovers from a container crash or an instance reboot without a human running a command - genuinely the most common single-instance failure mode, and now handled. What's *not* handled, deliberately: the instance itself going down (there is exactly one of it - no failover, no multi-AZ, nothing this issue's "single EC2 instance" scope would allow anyway) and application-level errors that don't crash the process (the healthcheck only catches "is `/health` reporting ok," not "is every feature working").

**Ease of maintenance**: the entire update procedure is `git pull && docker compose build && docker compose up -d` (Updating the application, above) - three commands, no new tooling to learn beyond what Docker Image Builds (Issue #56) already established. Logs, restarts, and rollback are all plain `docker compose`/`git` commands, deliberately not wrapped in a custom script - one more file to maintain and keep correct, for a sequence that's already short enough to document directly.

**Deferred limitations** - explicitly out of scope for this issue, per its own notes, not overlooked:

| Deferred | Why it matters eventually | What exists today instead |
|---|---|---|
| HTTPS / TLS | Traffic (including login credentials and JWTs) travels in plaintext | None - synthetic data only (see `docs/design-decisions.md` Decision 8), so the practical exposure is low for this project specifically, but this would be a hard blocker for any real deployment handling real data |
| DNS / custom domain | The app is only reachable by raw IP, which changes if the instance is ever replaced | None |
| Reverse proxy | Currently two ports to expose and remember instead of one; also a prerequisite for HTTPS (e.g. Caddy/nginx with Let's Encrypt) | None - see Deployment Architecture above |
| Automated deployment | "Deploy" (Continuous Deployment's step 7) is a manual SSH session today, not triggered by merging to `main` | The manual procedure in Updating the application, above |
| Monitoring / alerting | Nothing pages anyone if a container is unhealthy for an extended period | `docker compose ps`/`GET /health`, checked by hand |
| Backups | `docker compose down -v` (or any volume loss) is unrecoverable data loss | The named volume persists across container/instance restarts (verified - see Manual Verification), but nothing protects against genuine volume loss. Uploaded *files* specifically have a better story once S3 is configured (Issue #58, below) - S3 durability is independent of this EC2 instance entirely - but the *metadata* pointing to them (`ClinicalDocument.storage_key`, in Postgres) is not, so losing the database volume still means those S3 objects become unreachable through the application even though the bytes themselves survive |
| Managed database (RDS) | A single Postgres container has no automated failover or point-in-time recovery | The `postgres` container + named volume, as deployed |
| Kubernetes / ECS / EKS | Out of scope for this issue by explicit instruction, and unnecessary at this project's actual scale (one instance, one of each container) | Docker Compose, as it already was |

---

## File Storage (S3) (Issue #58)

Uploaded clinical document files (the original `.txt`/`.pdf`/`.csv`, not just their extracted text) are stored through a pluggable `StorageService` - see `docs/architecture.md`'s Storage Abstraction section for the interface and both implementations. This section is the operational half: creating a bucket, its IAM policy, and the environment variables that select and configure S3 in a real deployment.

### Choosing a backend

`STORAGE_BACKEND` (default `local`) selects which `StorageService` implementation the backend uses - set via `infra/.env` (Docker Compose - see `infra/.env.example`) or `backend/.env` (running the backend directly - see `backend/.env.example`). Switching it is a configuration change, never a code change:

| `STORAGE_BACKEND` | Where files go | Survives the container being recreated? | Extra configuration needed |
|---|---|---|---|
| `local` (default) | Inside the backend container's own filesystem (`LOCAL_STORAGE_DIR`, default `./storage/clinical_documents`) | No - lost on every `docker compose up`/redeploy that recreates the backend container (see Updating the application, above) | None |
| `s3` | A private S3 bucket | Yes - independent of the EC2 instance and its containers entirely | `AWS_REGION`, `S3_BUCKET_NAME` (required); `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (only for local testing against a real bucket - see Security below) |

`local` is fine for trying the application out; **`s3` is what a real deployment should use**, since local storage is silently lost the next time the backend container is recreated - exactly the kind of file loss "Updating the application" (above) causes routinely and doesn't otherwise warn about.

If `STORAGE_BACKEND=s3` is set without `AWS_REGION` or `S3_BUCKET_NAME`, the backend **fails to start** with a clear error naming exactly which variable is missing (`Settings`'s own startup validation, `backend/app/core/config.py`) - not a runtime failure on the first upload.

### Creating the bucket

```bash
aws s3api create-bucket \
  --bucket medlens-documents-<something-unique> \
  --region us-east-1

# Block all public access - defense in depth alongside the private ACL
# every upload already sets (see docs/architecture.md).
aws s3api put-public-access-block \
  --bucket medlens-documents-<something-unique> \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

S3 bucket names are globally unique across all of AWS, not just your account - `<something-unique>` needs to be genuinely unique (e.g. a suffix from `uuidgen` or your AWS account id), and is otherwise unconstrained by this application (`S3_BUCKET_NAME` accepts whatever name the bucket was actually created with).

### IAM permissions

The backend needs exactly three S3 actions, scoped to this one bucket - never broader `s3:*` or account-wide access:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::medlens-documents-<something-unique>/*"
    }
  ]
}
```

`s3:DeleteObject` is included because `DELETE /patients/{patient_id}/clinical-documents/{document_id}` deletes the S3 object along with the database row (`docs/api.md`). No `s3:ListBucket` is needed - every operation this application performs (`upload`/`download`/`delete`) addresses a specific, already-known key; it never lists a bucket's contents.

**Recommended: an IAM role attached to the EC2 instance**, not a long-lived access key pair - this is what this feature's own "use IAM credentials" requirement means in practice, and it's also what `S3StorageService`'s credential handling is built around (see `docs/architecture.md`): leave `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` unset in `infra/.env`, and `boto3` picks up the role automatically via EC2 instance metadata, with nothing to rotate and nothing that could leak from a config file. Attach the policy above to a role, then attach that role to the EC2 instance (via an instance profile) at launch or afterward.

### Environment variables

Already covered in the Environment Variables table under Docker Image Builds, above; summarized here for the S3-specific ones:

| Variable | Required when `STORAGE_BACKEND=s3` | Notes |
|---|---|---|
| `AWS_REGION` | Yes | The bucket's region, e.g. `us-east-1`. |
| `S3_BUCKET_NAME` | Yes | Must already exist - this application never creates a bucket itself. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | No | Leave both unset on a real deployment (see IAM role, above). Only set for local development against a real bucket using your own AWS credentials - never commit real values. |

### Local development against a real bucket

Local development defaults to `STORAGE_BACKEND=local` and needs no AWS account at all. To test against a real S3 bucket instead, set in `backend/.env` (running the backend directly) or `infra/.env` (Docker Compose):

```bash
STORAGE_BACKEND=s3
AWS_REGION=us-east-1
S3_BUCKET_NAME=medlens-documents-<something-unique>
AWS_ACCESS_KEY_ID=<your own AWS access key>
AWS_SECRET_ACCESS_KEY=<your own AWS secret key>
```

### Security

- **Never public.** Every uploaded object is stored with `ACL="private"` (`app/storage/s3.py`), and the bucket itself should additionally block public access at the account level (`put-public-access-block`, above) - two independent layers, so a mistake in either alone doesn't make an object public.
- **No public object URLs, ever.** `GET .../{document_id}/download` (`docs/api.md`) streams the file's bytes through the backend process itself; the response is never a redirect to an S3 URL (pre-signed or otherwise), and no endpoint anywhere returns a bucket URL or object key to the client.
- **IAM credentials, not long-lived keys**, in production - see IAM permissions above.
- **Least-privilege policy** - `PutObject`/`GetObject`/`DeleteObject` scoped to one bucket's objects only, nothing account-wide.
- **Content type and filename validation are unchanged by this feature** - `upload-txt`/`upload-pdf`/`upload-csv` still validate extension/content-type/encoding/extractability exactly as before Issue #58 (`docs/api.md`); a file that fails any of those checks is rejected before storage is ever touched.
- **No AWS credential is ever logged.** Verified directly: `tests/test_storage_service.py::test_s3_credentials_are_never_included_in_a_raised_error_message` asserts a fake secret key and access key id never appear in a raised `StorageError`'s message, and `S3StorageService`/`LocalStorageService` never call `logger` with anything credential-shaped - the only things logged anywhere in the storage path are object keys and generic failure descriptions (`app/services/clinical_document_service.py`, `app/api/routes/clinical_documents.py`).

---

## Continuous Deployment

The planned deployment workflow is:

1. Push changes to a feature branch.
2. Open a pull request.
3. Run automated tests (Issues #54/#55).
4. Merge into `develop`.
5. Merge release into `main`.
6. Build Docker images (Issue #56, in CI - proves they build, doesn't deploy them).
7. Deploy the latest version to AWS EC2 (Issue #57, above - currently a manual `git pull` + rebuild over SSH, not yet triggered automatically by step 4/5. See Production Readiness below for what an automated version of this step would need.).

---

## Monitoring

What exists today: `GET /health` (checked manually - see Verifying the deployment above), Docker-level `healthcheck`s for all three containers (`docker compose ps` shows current status), and plain container logs (`docker compose logs`). No structured/shipped logging, request tracing, or processing-time metrics exist yet - see "AWS EC2 Deployment"'s Production Readiness subsection above for why this is an explicitly deferred limitation rather than an oversight.

Future improvements may include:

- AWS CloudWatch
- Sentry
- Performance dashboards
- Structured (JSON) application logs, shipped somewhere queryable

---

## Future Improvements

Potential production improvements include, roughly in the order they'd likely matter (see "AWS EC2 Deployment"'s Production Readiness subsection above for the full reasoning behind each):

- HTTPS / TLS and a reverse proxy
- A custom domain
- Automated (CI-triggered) deployment
- Backups
- Monitoring / alerting
- AWS RDS (managed PostgreSQL)
- Redis
- Celery background workers
- Load balancing / auto-scaling / blue-green deployments
- Kubernetes (only if the project ever genuinely outgrows a single instance - not a goal in itself)

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

Docker image builds (Issue #56) and the AWS EC2 deployment itself (Issue #57) are both implemented, as documented above. This document will continue to evolve as the deferred items listed under Production Readiness (above) are picked up.