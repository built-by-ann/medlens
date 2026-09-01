# Deployment

## Overview

MedLens is deployed as a Dockerized full-stack web application on AWS. The deployment emphasizes reproducibility and simplicity appropriate to a single-developer project over scalability: one EC2 instance, running the same three containers (`frontend`, `backend`, `postgres`), both locally and in CI, coordinated by the same Docker Compose file used for local development. A fourth container, `certbot`, exists in the same file but never runs continuously, only on demand, to issue or renew the HTTPS certificate `frontend` serves.

The production Docker images build reliably both locally and in CI (see Docker Image Builds, below), and those same images run in production on a real EC2 instance (see AWS EC2 Deployment, below). nginx sits in front of the backend (see Reverse Proxy, below), so the browser reaches the whole application through one origin, and that same nginx terminates a real TLS certificate (see HTTPS / TLS, below). A custom domain actually resolving to this instance, managed databases, and container orchestration (ECS/EKS/Kubernetes) remain explicitly deferred; see the Production Readiness subsection for the full list and why each is deferred rather than overlooked.

---

## Deployment Architecture

The current production environment consists of:

- React frontend (served as a static build by nginx, which also terminates HTTPS and reverse-proxies API requests to the backend, see Docker Strategy, Reverse Proxy, and HTTPS / TLS below)
- FastAPI backend, reachable only from inside the Docker network, never directly from the browser
- PostgreSQL database
- Docker containers, coordinated by Docker Compose
- A single AWS EC2 instance

See the "AWS EC2 Deployment" section below for the full architecture diagram and deployment runbook, the "Reverse Proxy" section for how the frontend and backend are served under one origin, and the "HTTPS / TLS" section for how that one origin is served securely.

---

## Local Development

Local development uses Docker Compose (`infra/docker-compose.yml`) to ensure every service can be started consistently.

Containers:

- `frontend`: the production image (Vite build served by nginx, see Docker Image Builds below). Local frontend *development* still uses `npm run dev` (see the root `README.md`), which hot-reloads and doesn't require Docker at all; this container exists to validate and run the deployable image, not to replace that faster loop.
- `backend`
- `postgres`

The application is runnable with:

```bash
cd infra
docker compose up --build
```

| Service | Host port | Container port |
|---|---|---|
| `frontend` | `80` and `443` | `80` and `443` (nginx) |
| `backend` | `127.0.0.1:8000` only | `8000` |
| `postgres` | `127.0.0.1:5432` only | `5432` |
| `certbot` | none: never publishes a port, and never starts with `docker compose up` at all (see HTTPS / TLS below) | n/a |

`frontend` is the only one of the four meant to be opened in a browser (`http://localhost/`, which immediately redirects to `https://localhost/`, see HTTPS / TLS below for why a browser will show a certificate warning here in local development, expected and harmless); it serves the SPA and reverse-proxies `/api/*` to `backend` (see Reverse Proxy below), so every request the app makes goes through it too, at the same origin. `backend`'s own port still exists for direct access (`curl`, Postman, `npm run dev`'s Vite dev server), but is bound to `127.0.0.1`, not published beyond the host, the same treatment `postgres` already had. `certbot` is never opened in a browser at all and isn't started by `docker compose up` in the first place.

`docker compose down` stops and removes the containers and network; add `-v` to also remove the named Postgres volume (`medlens_postgres_data`) and start from an empty database next time.

---

## Production Environment

The current production deployment (see "AWS EC2 Deployment" below for the full runbook) includes:

- Dockerized frontend (nginx, terminating HTTPS and reverse-proxying to the backend) and backend, each with a Docker-level health check and `restart: unless-stopped`
- PostgreSQL, with its data on a named Docker volume that survives container restarts and `docker compose down` (without `-v`)
- Configuration and secrets via environment variables (`infra/.env`, gitignored; never a value hardcoded in a tracked file)
- Database migrations applied automatically on every backend container start
- Application logs via `docker compose logs` (plain container stdout/stderr, no structured/shipped logging yet, see Production Readiness below)
- HTTPS via a real Let's Encrypt certificate, once `certbot` has actually been run against a domain that resolves to this instance; see HTTPS / TLS below

Deferred to a future iteration; see "AWS EC2 Deployment" below's Production Readiness subsection for the full reasoning behind each:

- DNS / a custom domain actually resolving to this instance (a prerequisite for HTTPS / TLS to do anything beyond what's already implemented; see HTTPS / TLS below)
- Load balancing / multiple instances
- Managed PostgreSQL (AWS RDS)
- Automated (CI-triggered) deployment
- Monitoring, alerting, and backups

---

## Environment Variables

Every environment variable `infra/docker-compose.yml` reads is documented in one place: the complete reference table under Docker Image Builds, below. It covers all 22 variables Compose actually substitutes (`VITE_API_BASE_URL`, `DATABASE_URL`, `JWT_SECRET_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `AI_PROVIDER`, `HUGGINGFACE_API_KEY`, `OPENBIOLLM_MODEL`, `MEDGEMMA_MODEL`, `APP_ENV`, `POSTGRES_PASSWORD`, `FRONTEND_PORT`, `FRONTEND_HTTPS_PORT`, `DOMAIN`, `BACKEND_PORT`, `STORAGE_BACKEND`, `AWS_REGION`, `S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `APP_VERSION`, and `LOG_LEVEL`), each with where it's needed, whether it's required, and its default. Sensitive values are never committed to the repository: real values live only in `infra/.env` (gitignored), never in `docker-compose.yml` itself; only `infra/.env.example` (placeholders) is tracked.

`CORS_ALLOWED_ORIGINS` no longer exists; see the Reverse Proxy section below for why. See Docker Image Builds below for the full table, including the one variable that's a Docker *build* argument rather than a container-runtime one.

---

## Docker Strategy

Each major component has its own Dockerfile:

- `backend/Dockerfile`, multi-stage: a `builder` stage installs Python dependencies with pip, a slim runtime stage copies only the installed packages and application code, and runs as a dedicated non-root user.
- `frontend/Dockerfile`, multi-stage: a Node `builder` stage runs the same `npm ci && npm run build` CI already runs, an `nginx:alpine` runtime stage serves the resulting static files, with an SPA fallback route so client-side routes survive a direct load or refresh, and a reverse proxy for `/api/*` to the backend. See `frontend/nginx.conf` and the Reverse Proxy section below.
- `postgres` uses the stock `postgres:16` image directly, no Dockerfile of its own.

Docker Compose (`infra/docker-compose.yml`) coordinates all three for local development. See Docker Image Builds below for build commands, environment variables, and the full set of decisions behind both Dockerfiles.

---

## Continuous Integration

- `.github/workflows/frontend.yml` runs on every push and pull request to `main`/`develop` that touches the frontend: `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm test`, and `npm run build`, in that order, on `ubuntu-latest` with Node 20. See `docs/frontend.md`'s "Continuous Integration" section for the full breakdown.
- `.github/workflows/backend.yml` runs the same way for the backend: `ruff format --check .`, `ruff check .`, and `pytest -v`, against a `postgres:16` service container, on `ubuntu-latest` with Python 3.12. See `docs/testing.md`'s "Continuous Integration" section for the full breakdown, including why `GEMINI_API_KEY` is deliberately left unset.

**Docker image builds** are the final step of each workflow above, not a third workflow: `docker build` for the matching Dockerfile, after every existing check has already passed. See Docker Image Builds below.

---

## Docker Image Builds

Building the production Docker images and running them in production are two separate concerns. This section covers building: proving the production Docker images always build, both locally and in CI, before they're ever relied on for a real deploy. Building alone doesn't deploy anything to AWS, doesn't add monitoring, and doesn't change how the application behaves; it only governs whether the two deployable images can be trusted to build.

Both `backend/Dockerfile` and `frontend/Dockerfile` exist and build successfully, matched by a `.dockerignore` in each directory. Without it, a real `docker build`'s `COPY . .` would copy a developer's actual local secrets straight into an image layer: `backend/.env` (`DATABASE_URL`, `JWT_SECRET_KEY`, `GEMINI_API_KEY`) and bulky local-only directories (`.venv`, `.pytest_cache`, `.ruff_cache`) on the backend side, `.env` and `node_modules` on the frontend side, so `.dockerignore` is treated as a security control, not a cleanup nice-to-have (see Design Decisions below). `infra/docker-compose.yml`'s `backend` service sets `JWT_SECRET_KEY` directly, the same way `backend.yml`'s CI job does, with the same non-secret placeholder reasoning: `Settings()` (`app/core/config.py`) requires it with no default, so it must come from an explicit, tracked source rather than an accident of what happens to be on disk.

### Building the images locally

```bash
# Backend
cd backend
docker build -t medlens-backend .

# Frontend (VITE_API_BASE_URL defaults to http://localhost:8000 if omitted,
# see Environment Variables below)
cd frontend
docker build -t medlens-frontend .

# Both, plus postgres, via Compose
cd infra
docker compose build
docker compose up --build
docker compose down       # add -v to also drop the postgres volume
```

A clean rebuild (`docker build --no-cache`) was verified to succeed for both images: the build only depends on `requirements.txt`/`package-lock.json` and the application source, never on a previous build's cache being present.

### Environment Variables

| Variable | Where it's needed | Required | Notes |
|---|---|---|---|
| `VITE_API_BASE_URL` | Frontend **image build** (`docker build --build-arg`) | No, defaults to `/api` | Vite inlines `import.meta.env.VITE_API_BASE_URL` into the built JS bundle at build time, not at container start, so unlike a typical server-side app, this can't be changed by restarting the container with a different environment variable. A relative path, not an absolute URL: the browser reaches the backend through this same nginx container's own reverse proxy (see Reverse Proxy below), so the default works unmodified for any deployment; there is normally no reason to override it. |
| `DATABASE_URL` | Backend **container runtime** | Yes | `infra/docker-compose.yml` builds this from `POSTGRES_PASSWORD` below and the `postgres` service's in-network address; set `POSTGRES_PASSWORD`, not `DATABASE_URL` itself, when using Compose. |
| `JWT_SECRET_KEY` | Backend **container runtime** | Yes | `infra/docker-compose.yml` defaults to a placeholder value. **The AWS EC2 Deployment section below covers overriding this (and every variable in this table) via `infra/.env` for a real deployment**; never edit `docker-compose.yml` itself to set a real secret. |
| `GEMINI_API_KEY` | Backend **container runtime** | No | AI features return a `503` with a clear error when unset (see `docs/api.md`) rather than the container failing to start. |
| `GEMINI_MODEL` | Backend **container runtime** | No, defaults to `gemini-2.5-flash` | Which Gemini model to call; see `docs/ai.md`'s "A Note on Model Retirement." Changing this only needs `infra/.env` updated and the backend container restarted (`docker compose up -d backend`), never a rebuild, useful when Google retires the current default, which has already happened once (`gemini-2.0-flash`, fixed by changing this same default). |
| `AI_PROVIDER` | Backend **container runtime** | No, defaults to `gemini` | Which `AIProvider` `get_ai_summary_service()` constructs: `gemini`, `openbiollm`, or `medgemma` (see `docs/ai.md`). The backend fails to start with a clear error if set to anything else, the same fail-fast treatment `STORAGE_BACKEND` gets. |
| `HUGGINGFACE_API_KEY` | Backend **container runtime** | Only when `AI_PROVIDER=openbiollm` or `AI_PROVIDER=medgemma` | A Hugging Face user access token (fine-grained, scoped to "Make calls to Inference Providers"), shared by both providers. Optional at the application level even when selected: the backend starts normally without it, and only an analysis request returns a `503` with a clear error, the same tradeoff `GEMINI_API_KEY` already makes. For `medgemma`, the account behind this token must also have accepted Google's "Health AI Developer Foundations" license terms on the model's Hugging Face page, a manual, one-time, account-level step this application does not perform on its behalf (see `docs/ai.md`). |
| `OPENBIOLLM_MODEL` | Backend **container runtime** | No, defaults to `aaditya/Llama3-OpenBioLLM-8B` | Which OpenBioLLM checkpoint to call, via Hugging Face's Inference Providers (see `docs/ai.md`). Only relevant when `AI_PROVIDER=openbiollm`; a plain runtime variable so a future change in which provider serves this checkpoint doesn't require a code change or rebuild. |
| `MEDGEMMA_MODEL` | Backend **container runtime** | No, defaults to `google/medgemma-27b-text-it` | Which MedGemma checkpoint to call, via Hugging Face's Inference Providers (see `docs/ai.md`). Only relevant when `AI_PROVIDER=medgemma`; a plain runtime variable for the same reason `OPENBIOLLM_MODEL` is. |
| `APP_ENV` | Backend **container runtime** | No, defaults to `development` | `development` auto-allows any `localhost`/`127.0.0.1` origin for CORS (see `app/main.py`'s `configure_cors`), relevant only to `npm run dev`'s Vite dev server, which talks to the backend directly and cross-origin. A real deployment should still set this to `production`, but not for CORS reasons anymore; see Reverse Proxy below. |
| `POSTGRES_PASSWORD` | Backend + `postgres` **container runtime** | No, defaults to `medlens_password` | `infra/docker-compose.yml` references this one variable in both the `postgres` service's own credentials and the backend's `DATABASE_URL`, so they can't drift out of sync. Change it before any real deployment. |
| `FRONTEND_PORT` | Host, at `docker compose up` time | No, defaults to `80` | Which host port Compose publishes the frontend container's HTTP listener on: redirects to HTTPS and serves Let's Encrypt's renewal challenge only, not the app itself. Not read by the application itself. |
| `FRONTEND_HTTPS_PORT` | Host, at `docker compose up` time | No, defaults to `443` | Which host port Compose publishes the frontend container's HTTPS listener on: the actual public entry point once HTTPS is set up. See HTTPS / TLS below. |
| `DOMAIN` | Frontend **image build** (`docker build --build-arg`) | No, defaults to `medlenshealth.com` | Baked into `nginx.conf` at build time (same reasoning as `VITE_API_BASE_URL` above), so nginx knows which path inside the shared certificate volume to read from. Must match the domain `certbot` actually issues a certificate for; see HTTPS / TLS below. |
| `BACKEND_PORT` | Host, at `docker compose up` time | No, defaults to `8000` | Bound to `127.0.0.1` only, never reachable from outside the host. Exists for direct local access to the API (`curl`, Postman, `npm run dev`), not for the browser, which only ever uses the reverse proxy above. |
| `STORAGE_BACKEND` | Backend **container runtime** | No, defaults to `local` | `local` or `s3`; see the "File Storage (S3)" section below for the full setup. |
| `AWS_REGION` / `S3_BUCKET_NAME` | Backend **container runtime** | Only when `STORAGE_BACKEND=s3` | The backend fails to start with a clear error if either is missing while `s3` is selected; see "File Storage (S3)" below. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Backend **container runtime** | No | Leave unset in production; an IAM role attached to the EC2 instance is used instead. Only set for local development against a real bucket. See "File Storage (S3)" below. |
| `APP_VERSION` | Backend **container runtime** | No, defaults to `1.0.0` | A plain configured string reported by `GET /health` (`docs/api.md`), not derived from git or the image tag. Set it to whatever version identifier is meaningful for your deployment process. |
| `LOG_LEVEL` | Backend **container runtime** | No, defaults to `INFO` | Root logger level; see "Structured Application Logging" below. |

The distinction in the first row, a frontend *build* argument versus every other variable being a *runtime* one, is the one genuinely non-obvious piece of configuration to get right, and is why `frontend/Dockerfile`'s `ARG`/`ENV` pair and `frontend.yml`'s `--build-arg` flag exist at all (see `docs/frontend.md`'s Continuous Integration section).

### Verifying CI without pushing a commit

`.github/workflows/backend.yml` and `.github/workflows/frontend.yml` were both checked with [`actionlint`](https://github.com/rhysd/actionlint) (`actionlint .github/workflows/*.yml`), which validates GitHub Actions workflow syntax and semantics beyond plain YAML parsing (unknown keys, bad expression syntax, shell-script issues inside `run:` steps via its bundled `shellcheck`); both files pass with no findings.

### Design decisions

See `docs/design-decisions.md` (Decision 18) for the full reasoning behind each Dockerfile's shape: multi-stage builds, running the backend as a non-root user, why `frontend/Dockerfile` serves the build with nginx rather than `npm run preview` or a Node static-file server, and why `.dockerignore` was treated as a security fix rather than a cleanup nice-to-have.

### Build Performance

Both Dockerfiles use multi-stage builds, and dependency installation (`pip install` / `npm ci`) is copied and run in its own layer *before* application source is copied in, so a source-only change (the overwhelming majority of commits) skips reinstalling dependencies entirely via Docker's own layer cache, verified directly: this takes ~1.4s locally.

On top of that:

- **BuildKit cache mounts** (`--mount=type=cache`) for both `pip install` and `npm ci`, plus a `# syntax=docker/dockerfile:1` pragma at the top of each Dockerfile so the mount syntax is recognized consistently regardless of Docker Engine version. A cache mount is never included in the exported image layer (unlike a normal on-disk cache directory would be), so the final image is unchanged, but the downloaded packages persist *between* builds in BuildKit's own cache store: a build that changes only one line of `requirements.txt`/`package-lock.json` reuses every already-downloaded wheel/tarball instead of redownloading from PyPI/npm. This is what lets `backend/Dockerfile` drop `pip install`'s `--no-cache-dir` flag (see Design Decisions below) without reintroducing the cache-bloats-the-image problem that flag exists to prevent; see `docs/design-decisions.md` (Decision 23).
- **GitHub Actions cache** (`type=gha`) for the "Validate Docker image build" step in both `backend.yml` and `frontend.yml`, via `docker/setup-buildx-action` + `docker/build-push-action` in place of a plain `docker build`. This is the change with the largest real-world effect: a CI job starts on a fresh runner with no prior Docker state at all, so the cache mounts above are only useful if something persists them across builds; locally that's BuildKit's own on-disk cache, but in CI nothing filled that role without this. `type=gha` stores and restores that same cache (layers and mount contents both) via GitHub's Actions cache, so an unchanged Dockerfile/dependency file skips reinstalling entirely on the next CI run, the same way a local rebuild already does.
- **`.dockerignore` additions**: `.mypy_cache/`, coverage artifacts, and editor directories (`.vscode/`, `.idea/`) in both, defensively; none are currently produced by this project (no mypy or coverage tooling configured, see `docs/testing.md`), but excluding them costs nothing and avoids surprises if either is added later.

`infra/docker-compose.yml` needs no changes for any of this: it already just points at each Dockerfile's context, and Compose's own build machinery (BuildKit-backed by default) picks up the cache-mount changes above with no compose-level configuration needed. Runtime behavior, healthchecks, `depends_on`, restart policies, and networking are all independent of build-time caching.

---

## AWS EC2 Deployment

Where Docker Image Builds (above) covers "the images build," this section covers "the images run, in production, on a real EC2 instance, using Docker Compose." It reuses exactly those images and `infra/docker-compose.yml`, not a redesign. Deliberately out of scope, and covered instead under Production Readiness below as intentionally deferred work: DNS/a custom domain actually resolving here, ECS/EKS/Kubernetes, and automated (CI-triggered) deployment. A reverse proxy and HTTPS/TLS are implemented; see the Reverse Proxy and HTTPS / TLS sections below. This is a single EC2 instance, reached directly by IP (or, once DNS is configured, a domain) over HTTPS, updated by hand over SSH.

### Deployment architecture

```text
                        Internet
                            │
              ┌─────────────┼─────────────┐
              │ security group             │
              │   22 (SSH)   80   443      │
              └─────┬────────┬───────┬─────┘
                    ▼        ▼       ▼
              ┌──────────────────────────────────────┐
              │            EC2 instance                │
              │                                         │
              │  frontend container (nginx) :80, :443    │
              │    ├─ :80  redirects to :443, serves    │
              │    │       the ACME renewal challenge   │
              │    ├─ :443 serves the built React SPA   │
              │    └─      reverse-proxies /api/* ──┐    │
              │                                      ▼    │
              │  backend container (uvicorn) :8000        │
              │    (127.0.0.1 only - not exposed          │
              │     through the security group)           │
              │  postgres container :5432                 │
              │    (127.0.0.1 only - not exposed          │
              │     through the security group)           │
              │  certbot container - not always running,   │
              │    invoked on demand for cert issuance/    │
              │    renewal (see HTTPS / TLS below)         │
              │                                         │
              │  docker compose (infra/)                │
              └───────────────┬─────────────────────────┘
                              ▼
                         Gemini API
```

nginx is the one thing the browser ever talks to: it serves the built React SPA directly and reverse-proxies `/api/*` requests to the backend over the Docker network (see the Reverse Proxy section below). The backend's own port is bound to `127.0.0.1`, the same treatment postgres has, and is not part of the security group at all, so nothing outside the instance can reach it directly.

### Prerequisites

- An AWS account with permission to launch an EC2 instance and edit its security group.
- An SSH key pair (create one in the EC2 console, or import an existing public key), needed to reach the instance at all.
- A Gemini API key, if AI features should work (optional, see the Environment Variables table above).

### Step 1: Launch an EC2 instance

1. EC2 console → **Launch instance**.
2. **AMI**: Ubuntu Server 22.04 LTS (or 24.04 LTS): these instructions assume Ubuntu's `apt`-based install; Amazon Linux 2023 works too but uses `dnf` and a different Docker install path.
3. **Instance type**: `t3.small` (2 GiB RAM) is the practical minimum: building the frontend image (`npm ci && vite build`, see `docs/deployment.md`'s Docker Image Builds section) is memory-hungry enough that `t3.micro`'s 1 GiB can OOM mid-build. `t3.medium` gives more headroom if the free tier doesn't matter.
4. **Key pair**: select the one from Prerequisites.
5. **Storage**: the default 8 GiB gp3 root volume is tight once Docker's image layers and build cache accumulate; 20 GiB avoids babysitting disk space.
6. **Security group**: create a new one now; configure it in the next step before launching, not after.

### Step 2: Configure the security group

See Security below for the reasoning; the rules themselves:

| Type | Port | Source | Purpose |
|---|---|---|---|
| SSH | 22 | Your own IP only (`My IP` in the console) | Administration. Never `0.0.0.0/0`: an SSH port open to the entire internet is scanned and attacked continuously. |
| Custom TCP | 443 (or `FRONTEND_HTTPS_PORT`, see below) | `0.0.0.0/0` | The web app itself: the SPA and, via nginx's reverse proxy, the API too (`/api/*`, see Reverse Proxy below). The actual public entry point once HTTPS is set up (see HTTPS / TLS below). |
| Custom TCP | 80 (or `FRONTEND_PORT`, see below) | `0.0.0.0/0` | Redirects to 443, and serves Let's Encrypt's renewal challenge (see HTTPS / TLS below); this can't be closed even after HTTPS is working, since certificate renewal depends on it staying reachable. |

**8000 (backend) and 5432 (Postgres) are both deliberately absent from this table**: `infra/docker-compose.yml` binds both to `127.0.0.1` only (see Docker Strategy above), so neither is reachable from outside the instance even if a security group rule mistakenly allowed it. Nothing to configure here; this is enforced at the Docker level, not the AWS level, on purpose; see Security below.

### Step 3: Install Docker and Docker Compose

SSH in, then run Docker's official convenience script (installs the Docker Engine, CLI, and the `docker compose` plugin together; this is genuinely the `docker compose` used throughout this document, not the older standalone `docker-compose` Python tool):

```bash
ssh -i /path/to/your-key.pem ubuntu@<ec2-public-ip>

curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

Log out and back in (`exit`, then SSH in again) for the group change to take effect; without it, every `docker` command below needs `sudo` in front of it. Confirm both are present:

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

Fill in, at minimum, `JWT_SECRET_KEY` and `POSTGRES_PASSWORD` (both required for a real deployment, see Security below), and set `APP_ENV=production`. That's it for this instance's own public address. `VITE_API_BASE_URL` doesn't need to be set at all: it defaults to the relative path `/api`, which is correct for every deployment since the browser reaches the backend through this same frontend's own reverse proxy (see Reverse Proxy below), never a separate host/port. There is nothing to know about this instance's public IP before building the frontend image. `infra/.env` is gitignored; it never gets committed, by this repository's own `.gitignore`, regardless of what's in it.

### Step 6: Build the images

```bash
docker compose build
```

This is the exact `docker build` already validated in CI for each image, run here against `infra/.env`'s real values instead of CI's/local dev's placeholders; `VITE_API_BASE_URL` is what actually gets baked into the frontend bundle this time.

### Step 7: Start the application

```bash
docker compose up -d
```

`-d` (detached) so the application keeps running after the SSH session ends; without it, closing the terminal stops every container. `restart: unless-stopped` on `frontend`/`backend`/`postgres` (see Production Configuration below) means they come back automatically if the instance itself reboots, with no manual step needed. `certbot` never starts here at all (see HTTPS / TLS below); `docker compose up` brings up exactly the same three always-running containers it always has.

At this point the app is already reachable over HTTPS, at `https://<ec2-public-ip>/`: `frontend`'s own `ensure-dummy-cert.sh` generates a short-lived self-signed certificate the moment nginx starts, specifically so this step alone is never blocked on DNS or Let's Encrypt being reachable. A browser will show a certificate warning until Step 8 below replaces it with a real one; nothing else is broken or waiting on that.

### Step 8: Enable real HTTPS

Only possible once your domain's DNS actually points at this instance's public IP (an A record, at whatever registrar/DNS provider you use for it, outside this repository, see Production Readiness below). Let's Encrypt validates domain control by connecting to port 80 on the domain itself, not the IP directly, so this step fails until that DNS change has propagated.

```bash
docker compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d medlenshealth.com \
  --email you@example.com --agree-tos --no-eff-email

docker compose exec frontend nginx -s reload
```

Replace the domain and email with your own if you're deploying this project under a different one, and make sure it's the *same* domain `DOMAIN` was set to in `infra/.env` before `docker compose build frontend` (Step 6), or nginx will be looking for the certificate in the wrong place inside the shared volume. `nginx -s reload` picks up the new certificate without dropping any in-flight connections; no container restart needed.

See HTTPS / TLS below for what this command actually did, and for the cron entry that keeps the certificate renewed afterward without repeating this step by hand every ~90 days.

### Verifying the deployment

```bash
# From the instance itself:
docker compose ps                     # frontend/backend/postgres should show "healthy" within ~30s
curl http://localhost:8000/health     # direct to the backend, 127.0.0.1 only, works from the instance itself
curl -k https://localhost/api/health  # through nginx, what the browser actually uses.
                                       # -k (skip certificate verification) only matters before Step 8;
                                       # once a real certificate is in place, drop it.

# From your own machine:
curl https://<ec2-public-ip-or-domain>/api/health   # add -k too, before Step 8
```

Every `/health` check returns the same body: `{"status":"ok","version":"1.0.0","environment":"production",...}` (see `docs/api.md`); the nginx-routed ones just additionally prove the reverse proxy (and, after Step 8, HTTPS itself) are working, not only the backend directly.

Then open `https://<ec2-public-ip-or-domain>/` in a browser. The app should load (with a certificate warning to click through, if Step 8 hasn't run yet), and registering an account should succeed (this exercises the database end to end, proving migrations actually ran; see Production Configuration below for why that specifically used to be broken). Open the browser's Network tab while doing this: every request should show as `https://.../api/...`, never a separate `:8000` origin or a plain `http://` request, and none should be preceded by an `OPTIONS` preflight request; see Reverse Proxy below for why on the CORS point, and HTTPS / TLS below for the redirect and certificate.

### Updating the application

```bash
cd ~/medlens
git pull
cd infra
docker compose build
docker compose up -d
```

`docker compose up -d` after a rebuild only recreates containers whose image actually changed: if just the backend changed, the frontend and postgres containers aren't touched (and keep running, with no downtime for them). Migrations run automatically as each backend container starts (see Production Configuration below), so a schema change ships as part of this same `git pull` + rebuild, with no separate migration step to remember.

### Rollback procedure

There's no automated rollback (out of scope, see Production Readiness below), but the manual version is a normal `git` operation followed by the same update steps:

```bash
cd ~/medlens
git log --oneline -10       # find the last known-good commit
git checkout <commit-sha>   # or: git checkout <previous-tag>
cd infra
docker compose build
docker compose up -d
```

**A rollback that crosses a database migration is the one case this doesn't handle for you.** Rolling the application code back to before a migration was added does not reverse that migration; the schema stays at whatever it was upgraded to. This is a real limitation, not an oversight: `alembic downgrade` exists and can reverse a specific migration by hand if truly needed, but running it against a production database is exactly risky enough that it shouldn't happen as an unattended part of a generic rollback command. If a deployed migration needs to be reversed, do it deliberately, one migration at a time, and back up the volume first (see Production Readiness below).

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
docker compose down -v             # also remove the postgres volume, genuinely destroys all data, only for
                                    # a real reset, e.g. rebuilding the whole environment from scratch
```

### Troubleshooting

- **A container shows `unhealthy` or keeps restarting.** `docker compose ps` shows which one; `docker compose logs <service>` almost always explains why. A backend stuck unhealthy immediately after a fresh `docker compose up` is most often `postgres` not being reachable yet: `depends_on: condition: service_healthy` (see Production Configuration below) should prevent this by making backend wait, but if `postgres` itself never reports healthy, check its own logs first.
- **`docker compose build` fails partway through, out of memory.** Most common on `t3.micro`: the frontend build (`npm ci && vite build`) is the usual culprit. Either resize the instance (Step 1) or add swap: `sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`.
- **A request fails with a CORS error in the browser console.** This should never happen against the deployed app at all: every request goes through nginx's own reverse proxy, same-origin, and CORS is only ever relevant to `npm run dev`'s Vite dev server (see Reverse Proxy below). If you're seeing this against a real deployment, check the browser's Network tab for what origin the failing request actually went to; it likely means the frontend image was built with a stale, absolute `VITE_API_BASE_URL` rather than the current default (`/api`); see the next bullet.
- **API calls in the browser go to the wrong place, e.g. a `:8000` origin instead of the app's own.** `VITE_API_BASE_URL` was overridden to something other than its default (`/api`) when the frontend image was built; there's normally no reason to set it at all anymore (see Environment Variables above). Fix `infra/.env` (remove the override, or set it back to `/api`) and **rebuild** (`docker compose build frontend`); restarting the container alone does nothing, since this value is baked into the JS bundle at build time.
- **`docker: permission denied` on every command.** The `usermod -aG docker` group change from Step 3 needs a fresh login to take effect: log out and back in (or run `newgrp docker` in the current shell as a one-session workaround).
- **Registering a user (or any database write) fails with a 500.** Almost certainly a missed migration: check `docker compose logs backend` for `alembic` output near the top of the log; a real error there (not just the normal "Running upgrade..." lines) means the schema didn't apply. This should be automatic on every backend start (see Production Configuration below), so a persistent failure here is worth investigating directly rather than working around.
- **Creating an analysis always fails with a 503, "Gemini request failed: ClientError."** Check `docker compose logs backend` for the accompanying `detail=` field (see the Logging paragraph in `docs/ai.md`'s Error Handling section): `"models/<name> is not found"` means Google has retired the configured model server-side, exactly what happened to `gemini-2.0-flash` in production. Fix: set `GEMINI_MODEL` in `infra/.env` to a current model name and restart the backend (`docker compose up -d backend`); no rebuild needed, this is a runtime variable (see Environment Variables above).

### Production Configuration

A genuine EC2 deployment needs more than an image that builds: the configuration below in `infra/docker-compose.yml`, `backend/Dockerfile`, and `backend/alembic/env.py` is what makes a real deployment work correctly and stay secure:

- **Database migrations run automatically.** `alembic.ini`'s `sqlalchemy.url` is a hardcoded `localhost:5432` connection string, correct only when `alembic` runs directly on a developer's host; it says nothing about how migrations should resolve a database inside a container. `backend/alembic/env.py` prefers `DATABASE_URL` from the environment over `alembic.ini`'s static value (so migrations resolve the right host whether run inside a container or on a developer's machine), and `backend/Dockerfile`'s `CMD` runs `alembic upgrade head` before starting `uvicorn` on every container start (a no-op against an already-current database, so this is safe on every restart, not just the first one), which is what lets a schema change ship as an ordinary part of "Updating the application" (below) with no separate migration step to remember. See `docs/design-decisions.md` (Decision 19).
- **Secrets are never hardcoded in `docker-compose.yml`.** A literal value committed in a tracked YAML file is by definition not something a real deployment can keep secret. `infra/docker-compose.yml` reads `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, `GEMINI_API_KEY`, `APP_ENV`, and `CORS_ALLOWED_ORIGINS` via `${VAR:-default}` substitution from `infra/.env` (gitignored the same way `backend/.env`/`frontend/.env` already are, see Security below), each defaulting to a non-secret placeholder, so local development and CI need no extra configuration at all.
- **Postgres's port is bound to `127.0.0.1` only.** `- "5432:5432"` in Docker Compose would bind to `0.0.0.0` by default: reachable from outside the host if a security group ever allowed it, which is one misconfiguration away from a public database. `infra/docker-compose.yml` instead uses `- "127.0.0.1:5432:5432"`: still reachable from the host itself (`psql -h localhost`, an SSH tunnel), never from outside it, regardless of the security group. See Security below.

All three services use `restart: unless-stopped` (so a container that crashes, or an instance that reboots, recovers without a manual `docker compose up`), and all three have Docker-level `healthcheck`s: `postgres` uses `pg_isready`, with a `start_period: 10s` (matching `backend`'s own value) to tolerate the brief startup/restart cycle Postgres's own entrypoint performs on a fresh volume: it runs `initdb`, then briefly starts and stops the server once as part of that process before starting it for real (standard behavior of the upstream `postgres:16` image), and `pg_isready` fails during that window, which is expected, not a real problem, so without a `start_period` those expected early failures would count toward `retries` like any other failure. `backend`'s healthcheck is an HTTP check that parses `/health`'s response body and checks `status == "ok"` directly, rather than trusting the HTTP status code alone: `/health` does return `503` on a real database failure (see `docs/api.md`), but reading the body's own `status` field is a more direct check of the thing that actually matters (is the database reachable), and keeps working unchanged regardless of what status code any future revision of this endpoint chooses to pair with a failure. `frontend`'s healthcheck is a plain `wget --spider` against nginx.

`backend` declares `depends_on: postgres: condition: service_healthy` rather than an unconditional `depends_on: - postgres`, which would only wait for the postgres *container* to start, not for Postgres itself to be ready to accept connections; this closes the transient "database disconnected" race a plain container-start dependency would leave open. `frontend`, by contrast, has no `depends_on: backend` at all: this container serves the prebuilt static SPA over nginx and nothing else at the container-start level, and `VITE_API_BASE_URL` is baked into the JS bundle at image build time, not read at container start, so there is no runtime dependency on `backend` being up, healthy, or even present to express. `postgres` and `frontend` start in parallel, with only `backend` waiting on `postgres`. This was verified with a full `docker compose up -d --build` from a clean state: `postgres` reaches `healthy` first, `backend` starts once `postgres` is healthy, and `frontend` starts immediately in parallel with both rather than waiting on `backend`.

### Reverse Proxy

nginx (already the frontend's own container, serving the built SPA, no separate component) sits in front of the backend as well: it reverse-proxies `/api/*` to the backend over the Docker network, and the browser never talks to the backend's own port at all. This is what lets the backend's port stay unpublished (see Security below) and removes any need for CORS configuration between frontend and backend in production. The alternative, where the browser talks to two separate origins (the frontend on its own port and the backend directly on `http(s)://<host>:8000`), would require the backend's port to be published publicly, the frontend to be told that URL at image build time, and the backend to have CORS configured to accept requests from the frontend's separate origin. See the Deployment Architecture diagram above for the request flow, and `docs/design-decisions.md` (Decision 24) for the full reasoning.

**Current configuration:**

- `frontend/nginx.conf` has a `location /api/` block that strips the `/api` prefix and proxies everything else to `backend:8000` over the Docker network, using Docker's embedded DNS resolver so it re-resolves `backend`'s address per request rather than caching it from nginx startup (needed because `backend` can be recreated with a new IP independently, e.g. during a rolling update, see Decision 24), plus a `client_max_body_size 25m` (nginx's own 1m default is smaller than a real clinical PDF upload) and the standard `X-Real-IP`/`X-Forwarded-For`/`X-Forwarded-Proto` headers.
- `backend/Dockerfile`'s `uvicorn` invocation includes `--forwarded-allow-ips='*'`, so it actually trusts and reads those headers; without it, every request's `client_ip` (in the structured logs, see Structured Application Logging below) would show nginx's own Docker-network address instead of the real visitor's. This is safe to trust unconditionally because the backend's port is not reachable by anything except nginx (and the host itself).
- In `infra/docker-compose.yml`: `backend`'s port binds to `127.0.0.1` only (the same treatment `postgres` has); `frontend`'s default host port is `80`; `VITE_API_BASE_URL`'s build-arg default is the relative path `/api`; there is no `CORS_ALLOWED_ORIGINS` variable. Healthchecks, `depends_on`, and restart policies are unaffected by any of this; `frontend` still has no `depends_on: backend` at all (see Production Configuration above), for the same "no runtime dependency to express" reasoning, which happens to also hold here (see Decision 24).
- `app/main.py`'s `configure_cors` has no `allowed_origins` parameter: `allow_origins` is always empty, since there is no legitimate cross-origin production request to allow for. The `LOCALHOST_ORIGIN_REGEX` behavior for `app_env == "development"` is retained: CORS middleware itself stays in place, not removed, because `npm run dev`'s Vite dev server still makes a real cross-origin request directly to the backend (see Local Development above).
- No frontend *source* code is involved in any of this: `frontend/src/api/client.ts`'s one shared axios instance builds every request from a configured `baseURL` plus a relative path (`/patients`, `/auth/login`, ...) with zero hardcoded hosts anywhere in the codebase, so pointing `VITE_API_BASE_URL` at a relative path (`/api`) is sufficient on its own; axios resolves a relative `baseURL` against the page's own origin automatically.

**Verified directly** (not just "the config looks right"): a full `docker compose up -d --build` from a clean state, then registering a user, logging in, and exercising patient/medication CRUD entirely through `http://localhost/api/...`, with identical responses to calling the backend's own port directly, and `client_ip` in the backend's own structured logs showing the real originating address, not nginx's container IP. Also verified the specific failure mode Decision 24 calls out: recreating *only* the `backend` container (`docker compose up -d --force-recreate backend`, simulating exactly what "Updating the application" above does on a backend-only change) leaves it with a new Docker-network IP, and `/api/health` through nginx keeps working afterward with no action taken on `frontend` at all. Separately, removing the `backend` container entirely and restarting `frontend` first confirmed nginx still starts and serves the SPA normally, `/api/*` correctly returning `502` (not a crash) until `backend` exists again.

### HTTPS / TLS

nginx terminates a real TLS certificate for the frontend's single origin. See `docs/design-decisions.md` (Decision 25) for the full reasoning behind the design below.

**Current configuration:**

- `frontend/nginx.conf` has two server blocks: port 80 only redirects to HTTPS (`308`, preserving the request method and query string) and serves Let's Encrypt's ACME HTTP-01 challenge at `/.well-known/acme-challenge/` (which must stay reachable over plain HTTP forever, not just during initial issuance; renewal re-validates the same way); port 443 carries everything else (the `/api/` proxy, SPA serving) plus TLS termination: `ssl_protocols TLSv1.2 TLSv1.3`, Mozilla's "Intermediate" cipher list, and a `Strict-Transport-Security` header (`max-age=15768000`, about 6 months, deliberately without `includeSubDomains` or `preload`, both of which are much harder to safely reverse than to add later).
- `frontend/Dockerfile` has a `DOMAIN` build arg (defaults to `medlenshealth.com`, overridable via `infra/.env`) baked into `nginx.conf` at build time, an `openssl` package (not present in `nginx:alpine` by default), and `ensure-dummy-cert.sh` installed into nginx's own `/docker-entrypoint.d/` auto-run mechanism: it generates a short-lived self-signed certificate at the same path `nginx.conf` expects, but only when nothing real is there yet, so `docker compose up` works identically whether or not a real certificate has ever been issued. This dummy-certificate bootstrap exists specifically so starting the stack is never blocked on DNS or Let's Encrypt being reachable (see Step 7 above).
- In `infra/docker-compose.yml`: `frontend` publishes `443` (`FRONTEND_HTTPS_PORT`) alongside `80`, and mounts two named volumes: `certbot_certs` (the certificate; read-write, since `ensure-dummy-cert.sh` needs to write the placeholder there too) and `certbot_www` (the ACME challenge webroot; read-only from `frontend`'s side). A `certbot` service, using the official `certbot/certbot` image and sharing both volumes, provides the real certificate, gated behind Compose's `profiles` so it never starts with a plain `docker compose up`, only via `docker compose run` (see Step 8 above for the actual commands); this keeps certificate issuance/renewal an explicit, on-demand action rather than something that runs unattended as part of every stack start. `frontend`'s healthcheck uses `https://127.0.0.1/` with `--no-check-certificate` (it only needs to confirm nginx is responding, not that the certificate is CA-trusted, true by design for the self-signed placeholder). `backend` and `postgres`, their healthchecks, `depends_on`, and restart policies are unaffected.
- No application code is involved: HTTPS termination happens entirely in nginx; the backend continues speaking plain HTTP over the Docker network, and `X-Forwarded-Proto` (forwarded correctly by the reverse proxy, see Reverse Proxy above) genuinely reads `https` for every real request.

**Certificate management and renewal:**

`certbot/certbot`'s webroot plugin is what Step 8 above actually invokes (`certonly --webroot -w /var/www/certbot -d medlenshealth.com`): it writes challenge files nginx serves from the shared `certbot_www` volume, Let's Encrypt fetches them over port 80 to confirm domain control, and the resulting certificate lands in `certbot_certs` at `/etc/letsencrypt/live/medlenshealth.com/`, the same path `nginx.conf` was built to read from. `docker compose exec frontend nginx -s reload` picks it up without dropping connections.

Renewal is a host-level cron entry, not a fourth always-running container: Let's Encrypt certificates are valid 90 days, and `certbot renew` is a no-op unless a certificate is actually close to expiring, so a frequent, idempotent cron job is the standard, low-risk approach:

```bash
# crontab -e, on the EC2 instance:
0 3,15 * * * cd ~/medlens/infra && docker compose run --rm certbot renew --quiet && docker compose exec frontend nginx -s reload
```

Twice daily (Certbot's own recommended frequency, to tolerate a transient failure without risking an actual expiry), redirected to run quietly: `certbot renew` already logs to `/var/log/letsencrypt` inside the volume on an actual attempt. The `nginx -s reload` only matters on the rare day a renewal actually happens; it's harmless (a no-op reload) every other day.

**Not verified in this environment**: actually obtaining a certificate from Let's Encrypt, since that requires `medlenshealth.com` to already resolve via DNS to a real, publicly-reachable instance; neither exists in this development environment (see Production Readiness below). What *is* verified directly: the entire path up to that point: `docker compose up -d --build` from a clean state, `frontend` reaching `healthy` on both ports, `http://localhost/` redirecting to `https://localhost/` (`308`), the self-signed placeholder certificate negotiating TLS 1.3 successfully, the `Strict-Transport-Security` header present, `/api/health` and a full register/login/patient-CRUD flow working identically over HTTPS as they did over plain HTTP, the ACME challenge location responding (`404` for a nonexistent token, not a redirect, proving it's correctly excluded from the HTTP→HTTPS redirect), `docker compose run --rm certbot certificates` executing correctly against the (empty, in this environment) certificate volume, and the dummy certificate persisting unchanged across a `frontend` container recreation (confirmed by an identical file checksum before and after) rather than being needlessly regenerated. Also confirmed `certbot` does not start with a plain `docker compose up`/`up -d --build` (Compose `profiles`), while `docker compose run --rm certbot ...` still reaches it by name regardless.

### Security

- **Containers run as non-root where applicable.** The backend runs as a dedicated `appuser` (`backend/Dockerfile`), verified with `docker exec <container> whoami` → `appuser`. The frontend's `nginx:alpine` runtime uses the standard nginx image as-is: its master process binds port 80 as root (required to bind a port below 1024) and hands actual request handling off to worker processes running as the unprivileged `nginx` user, nginx's own well-established privilege-separation model, not something this project's Dockerfile needs to (or should) override. `postgres:16` is the stock upstream image, whose own entrypoint already drops to a non-root `postgres` user.
- **Secrets are never committed.** `infra/.env` (real values) is covered by the repository's existing blanket `.env` rule in `.gitignore` (confirmed with `git check-ignore -v infra/.env`), the same rule that already covers `backend/.env`/`frontend/.env`. Only `infra/.env.example` (placeholders, no real values, the same pattern as `backend/.env.example`/`frontend/.env.example`) is tracked.
- **`.env` usage is documented** in Step 5 above and inline in `infra/.env.example` itself: every variable there has a comment explaining what it's for and, where it matters, whether changing it requires a rebuild (`VITE_API_BASE_URL`) or just a restart (everything else).
- **Security group configuration** is Step 2 above; summarized:

  | Port | Exposed to | Why |
  |---|---|---|
  | 22 (SSH) | Your IP only | Administration access. |
  | 443 (frontend, or `FRONTEND_HTTPS_PORT`) | Everyone | The whole application: the SPA and, via nginx's reverse proxy, the API too (see Reverse Proxy below). The actual public entry point once HTTPS is set up (see HTTPS / TLS below). |
  | 80 (frontend, or `FRONTEND_PORT`) | Everyone | Redirects to 443, and serves Let's Encrypt's renewal challenge; can't be closed even after HTTPS is working, since renewal depends on it. |
  | 8000 (backend, or `BACKEND_PORT`) | **Nobody** | Bound to `127.0.0.1` inside `docker-compose.yml`, not reachable from outside the instance even if a security group rule mistakenly allowed it, the same treatment Postgres has. The browser never uses this port; only nginx (over the Docker network) and, for direct local access, the instance itself. |
  | 5432 (Postgres) | **Nobody** | Bound to `127.0.0.1` inside `docker-compose.yml` itself (see Production Configuration above); there is no security group rule that could expose it even by mistake, since the port is never listening on a network interface a security group rule could apply to in the first place. |

### Production Readiness

**Reproducibility**: verified directly, not assumed. A fresh copy of this repository (simulating a clean `git clone`, no local Docker cache or state reused) built and ran successfully with zero configuration (every default in `infra/docker-compose.yml` kicking in), and separately with a real `infra/.env` overriding every secret, matching exactly what Step 5 above asks a real deployment to do. See Manual Verification in the final report for the full sequence.

**Reliability**: `restart: unless-stopped` and the three healthchecks (Production Configuration above) mean the stack recovers from a container crash or an instance reboot without a human running a command, genuinely the most common single-instance failure mode, and this is handled. What's *not* handled, deliberately: the instance itself going down (there is exactly one of it, no failover, no multi-AZ, consistent with a deliberate single-EC2-instance scope) and application-level errors that don't crash the process (the healthcheck only catches "is `/health` reporting ok," not "is every feature working").

**Ease of maintenance**: the entire update procedure is `git pull && docker compose build && docker compose up -d` (Updating the application, above): three commands, no tooling beyond what Docker Image Builds already establishes. Logs, restarts, and rollback are all plain `docker compose`/`git` commands, deliberately not wrapped in a custom script, since that would be one more file to maintain and keep correct, for a sequence that's already short enough to document directly.

**Deferred limitations**, explicitly out of scope for the current deployment, not overlooked:

| Deferred | Why it matters eventually | What exists today instead |
|---|---|---|
| DNS / custom domain actually resolving here | HTTPS / TLS (see above) is fully implemented, but can't issue a real certificate without a domain that resolves to this instance; until DNS is configured, the app is only reachable by raw IP, which also changes if the instance is ever replaced | The infrastructure to enable HTTPS the moment DNS exists; see HTTPS / TLS above, Step 8 |
| Automated deployment | "Deploy" (Continuous Deployment's step 7) is a manual SSH session today, not triggered by merging to `main` | The manual procedure in Updating the application, above |
| Monitoring / alerting | Nothing pages anyone if a container is unhealthy for an extended period | `docker compose ps`/`GET /health`, checked by hand |
| Backups | `docker compose down -v` (or any volume loss) is unrecoverable data loss | The named volume persists across container/instance restarts (verified, see Manual Verification), but nothing protects against genuine volume loss. Uploaded *files* specifically have a better story once S3 is configured (see File Storage (S3), below); S3 durability is independent of this EC2 instance entirely, but the *metadata* pointing to them (`ClinicalDocument.storage_key`, in Postgres) is not, so losing the database volume still means those S3 objects become unreachable through the application even though the bytes themselves survive |
| Managed database (RDS) | A single Postgres container has no automated failover or point-in-time recovery | The `postgres` container + named volume, as deployed |
| Kubernetes / ECS / EKS | Unnecessary at this project's actual scale (one instance, one of each container) | Docker Compose |

---

## File Storage (S3)

Uploaded clinical document files (the original `.txt`/`.pdf`/`.csv`, not just their extracted text) are stored through a pluggable `StorageService`; see `docs/architecture.md`'s Storage Abstraction section for the interface and both implementations. This section is the operational half: creating a bucket, its IAM policy, and the environment variables that select and configure S3 in a real deployment.

### Choosing a backend

`STORAGE_BACKEND` (default `local`) selects which `StorageService` implementation the backend uses, set via `infra/.env` (Docker Compose, see `infra/.env.example`) or `backend/.env` (running the backend directly, see `backend/.env.example`). Switching it is a configuration change, never a code change:

| `STORAGE_BACKEND` | Where files go | Survives the container being recreated? | Extra configuration needed |
|---|---|---|---|
| `local` (default) | Inside the backend container's own filesystem (`LOCAL_STORAGE_DIR`, default `./storage/clinical_documents`) | No, lost on every `docker compose up`/redeploy that recreates the backend container (see Updating the application, above) | None |
| `s3` | A private S3 bucket | Yes, independent of the EC2 instance and its containers entirely | `AWS_REGION`, `S3_BUCKET_NAME` (required); `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (only for local testing against a real bucket, see Security below) |

`local` is fine for trying the application out; **`s3` is what a real deployment should use**, since local storage is silently lost the next time the backend container is recreated, exactly the kind of file loss "Updating the application" (above) causes routinely and doesn't otherwise warn about.

If `STORAGE_BACKEND=s3` is set without `AWS_REGION` or `S3_BUCKET_NAME`, the backend **fails to start** with a clear error naming exactly which variable is missing (`Settings`'s own startup validation, `backend/app/core/config.py`), not a runtime failure on the first upload.

### Creating the bucket

```bash
aws s3api create-bucket \
  --bucket medlens-documents-<something-unique> \
  --region us-east-1

# Block all public access, defense in depth alongside the private ACL
# every upload already sets (see docs/architecture.md).
aws s3api put-public-access-block \
  --bucket medlens-documents-<something-unique> \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

S3 bucket names are globally unique across all of AWS, not just your account, so `<something-unique>` needs to be genuinely unique (e.g. a suffix from `uuidgen` or your AWS account id), and is otherwise unconstrained by this application (`S3_BUCKET_NAME` accepts whatever name the bucket was actually created with).

### IAM permissions

The backend needs exactly three S3 actions, scoped to this one bucket, never broader `s3:*` or account-wide access:

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

`s3:DeleteObject` is included because `DELETE /patients/{patient_id}/clinical-documents/{document_id}` deletes the S3 object along with the database row (`docs/api.md`). No `s3:ListBucket` is needed: every operation this application performs (`upload`/`download`/`delete`) addresses a specific, already-known key; it never lists a bucket's contents.

**Recommended: an IAM role attached to the EC2 instance**, not a long-lived access key pair. This is what `S3StorageService`'s credential handling is built around (see `docs/architecture.md`): leave `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` unset in `infra/.env`, and `boto3` picks up the role automatically via EC2 instance metadata, with nothing to rotate and nothing that could leak from a config file. Attach the policy above to a role, then attach that role to the EC2 instance (via an instance profile) at launch or afterward.

### Environment variables

Already covered in the Environment Variables table under Docker Image Builds, above; summarized here for the S3-specific ones:

| Variable | Required when `STORAGE_BACKEND=s3` | Notes |
|---|---|---|
| `AWS_REGION` | Yes | The bucket's region, e.g. `us-east-1`. |
| `S3_BUCKET_NAME` | Yes | Must already exist; this application never creates a bucket itself. |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | No | Leave both unset on a real deployment (see IAM role, above). Only set for local development against a real bucket using your own AWS credentials; never commit real values. |

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

- **Never public.** Every uploaded object is stored with `ACL="private"` (`app/storage/s3.py`), and the bucket itself should additionally block public access at the account level (`put-public-access-block`, above): two independent layers, so a mistake in either alone doesn't make an object public.
- **No public object URLs, ever.** `GET .../{document_id}/download` (`docs/api.md`) streams the file's bytes through the backend process itself; the response is never a redirect to an S3 URL (pre-signed or otherwise), and no endpoint anywhere returns a bucket URL or object key to the client.
- **IAM credentials, not long-lived keys**, in production; see IAM permissions above.
- **Least-privilege policy**: `PutObject`/`GetObject`/`DeleteObject` scoped to one bucket's objects only, nothing account-wide.
- **Content type and filename validation apply regardless of storage backend**: `upload-txt`/`upload-pdf`/`upload-csv` validate extension/content-type/encoding/extractability the same way for both (`docs/api.md`); a file that fails any of those checks is rejected before storage is ever touched.
- **No AWS credential is ever logged.** Verified directly: `tests/test_storage_service.py::test_s3_credentials_are_never_included_in_a_raised_error_message` asserts a fake secret key and access key id never appear in a raised `StorageError`'s message, and `S3StorageService`/`LocalStorageService` never call `logger` with anything credential-shaped; the only things logged anywhere in the storage path are object keys and generic failure descriptions (`app/services/clinical_document_service.py`, `app/api/routes/clinical_documents.py`).

---

## Structured Application Logging

See `docs/architecture.md`'s "Logging" section for how this is implemented; this section covers what's relevant when actually running or operating the application.

### Environment variables

| Variable | Default | Notes |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Passed straight to Python's `logging` as the root logger's level. `INFO` surfaces the per-request summary line and every application lifecycle event; `DEBUG` additionally surfaces third-party libraries' own debug output (e.g. SQLAlchemy query logs). |
| `APP_ENV` | `development` | Also documented under Docker Image Builds, above; also selects the log format: a readable `key=value` line in `development`, one JSON object per line otherwise. |

### Log format

**Production (`APP_ENV` anything other than `development`)**: one JSON object per line, e.g.:

```json
{"timestamp": "2026-08-04T18:07:52.854Z", "level": "INFO", "logger": "app.core.logging_config", "event": "http_request_completed", "message": "Request completed", "request_id": "5b7ee380-...", "method": "GET", "path": "/patients/1/clinical-documents", "status_code": 200, "duration_ms": 12.3, "client_ip": "203.0.113.4", "user_id": 42}
```

Pipe through `jq` for readability: `docker compose logs backend | jq -R 'fromjson? // .'` (the `// .` fallback passes through any non-JSON line, e.g. Alembic's own migration log lines, unchanged, rather than erroring).

**Development (`APP_ENV=development`, the Docker Compose default)**: one readable line per record:

```text
2026-08-04T18:07:52.854Z INFO     app.core.logging_config event=http_request_completed status_code=200 duration_ms=12.3 request_id=5b7ee380-... user_id=42
```

### Request tracing

Every response includes an `X-Request-ID` header (a fresh `uuid4` per request), matching the `request_id` field on every log line emitted while handling that request, useful for correlating a specific failed request (reported by its `X-Request-ID`) back to its exact log lines, including any `login_succeeded`/`document_uploaded`/`analysis_failed`/etc. event logged during it.

### Uvicorn's access log is disabled

The `backend` container's `CMD` runs `uvicorn ... --no-access-log` (`backend/Dockerfile`): the application's own request-logging middleware already logs exactly one structured line per completed request (`http_request_completed`), so uvicorn's own differently-formatted access log line is turned off rather than appearing as a confusing second line for the same request.

### Never logged

Passwords, JWTs, `Authorization` headers, AWS credentials, Gemini prompts, and clinical document/file content are never logged anywhere in the codebase, not filtered out after the fact, simply never passed to a `logger` call in the first place. As defense in depth, every log record is additionally rendered through a fixed field allowlist (`ALLOWED_FIELDS`, `app/core/logging_config.py`): a field outside that list is silently dropped even if some future call site passed it via `extra=`. See `docs/design-decisions.md`'s Decision 22 and `docs/architecture.md`'s Logging section for the full reasoning, and `backend/tests/test_logging_config.py`/`test_request_logging_middleware.py` for the tests verifying it.

### Viewing logs

Same commands as Viewing logs, above (`docker compose logs backend`, etc.); structured logging changes the *content* and *format* of what's logged, not how logs are viewed or where they go. Shipping logs somewhere queryable (e.g. CloudWatch) remains a future improvement; see Monitoring, below.

---

## Timing Metrics

Every meaningful operation logs its own duration as a `duration_ms` field (milliseconds, always a plain number, never a formatted string) on an existing structured log event, with no separate logging mechanism, no Prometheus/OpenTelemetry/CloudWatch metrics, and no database changes. This builds directly on Structured Application Logging (above): the same `docker compose logs backend | jq` workflow already documented there is how these are read, and `request_id` correlates every line from the same request.

| What | Event | Span |
|---|---|---|
| Total HTTP request | `http_request_completed` | The whole request, from the request-logging middleware. |
| AI provider request | `ai_request_succeeded` / `ai_request_failed` | Just the call to Gemini, from `GeminiProvider.generate_summary`. |
| Analysis processing | `analysis_completed` / `analysis_failed` | From `mark_analysis_processing` through reconciliation, i.e. everything `POST /patients/{id}/analyses` does after creating the `Analysis` row. Broader than, and includes, the AI provider span above. |
| Document upload processing | `document_uploaded` | The whole upload route handler: validation, extraction, storage upload, and persistence. Broader than, and includes, the two spans below. |
| Document text extraction | `document_text_extracted` | Just parsing/decoding (`pypdf` for PDF, a plain UTF-8 decode for txt/csv), logged uniformly across all three upload formats via `file_type`. |
| Storage upload | `storage_upload_completed` (success) / `s3_upload_failed` (failure) | Just the write to the backend (`S3StorageService.upload`'s `put_object` call, or `LocalStorageService.upload`'s file write), identified by `storage_backend` (`"s3"` or `"local"`) and `storage_key`. |

**Nested spans are intentional, not duplicate instrumentation.** A single analysis request produces several `duration_ms` values that each cover a different, overlapping scope, e.g. `ai_request_succeeded` (2412ms) < `analysis_completed` (2436ms, adds reconciliation) < `http_request_completed` (2453ms, adds routing/auth overhead) for the same request, all sharing one `request_id`. The same nesting applies to uploads: `document_text_extracted` < `document_uploaded` < `http_request_completed`. No event is logged twice under two different names for the same span.

**Identifiers**: every timing event carries whichever of `request_id`, `patient_id`, `analysis_id`, `document_id`, `provider`, `model`, `storage_backend`, `storage_key` actually apply to it, the same `ALLOWED_FIELDS` allowlist used by structured logging generally (see Structured Application Logging, above).

---

## Continuous Deployment

The planned deployment workflow is:

1. Push changes to a feature branch.
2. Open a pull request.
3. Run automated tests in CI (see `docs/testing.md` and `docs/frontend.md`'s Continuous Integration sections).
4. Merge into `develop`.
5. Merge release into `main`.
6. Build Docker images in CI (see Docker Image Builds, above; proves they build, doesn't deploy them).
7. Deploy the latest version to AWS EC2 (see AWS EC2 Deployment, above; currently a manual `git pull` + rebuild over SSH, not yet triggered automatically by step 4/5. See Production Readiness above for what an automated version of this step would need.).

---

## Monitoring

What exists today: `GET /health` (checked manually, see Verifying the deployment above), Docker-level `healthcheck`s for all three containers (`docker compose ps` shows current status), and structured application logs with per-request tracing (Structured Application Logging, above): one JSON line per completed request (`http_request_completed`, with `duration_ms`) plus every major lifecycle event (login, registration, document upload/deletion, analysis started/completed/failed, storage/AI provider failures), all correlatable by `request_id`/`X-Request-ID`. What's still missing: nothing pages anyone automatically, logs aren't shipped anywhere queryable (they're read via `docker compose logs`, not a log aggregator), and there are no aggregated performance dashboards; see "AWS EC2 Deployment"'s Production Readiness subsection above for why this is an explicitly deferred limitation rather than an oversight.

Future improvements may include:

- AWS CloudWatch
- Sentry
- Performance dashboards
- Shipping the existing structured (JSON) application logs somewhere queryable

---

## Future Improvements

Potential production improvements include, roughly in the order they'd likely matter (see "AWS EC2 Deployment"'s Production Readiness subsection above for the full reasoning behind each):

- A custom domain actually resolving to this instance (HTTPS / TLS and a reverse proxy are both implemented already; see the HTTPS / TLS and Reverse Proxy sections above)
- Automated (CI-triggered) deployment
- Backups
- Monitoring / alerting
- AWS RDS (managed PostgreSQL)
- Redis
- Celery background workers
- Load balancing / auto-scaling / blue-green deployments
- Kubernetes (only if the project ever genuinely outgrows a single instance, not a goal in itself)

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

Docker image builds and the AWS EC2 deployment itself are both implemented, as documented above. This document will continue to evolve as the deferred items listed under Production Readiness (above) are picked up.