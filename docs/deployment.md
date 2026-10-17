# Deployment

MedLens runs as Docker Compose on a single AWS EC2 instance. The same `infra/docker-compose.yml` is used locally and in production.

```text
Internet ──▶ security group (22, 80, 443)
                │
                ▼
   ┌──────── EC2 instance ─────────────────────────┐
   │  frontend (nginx) :80 → redirect to :443       │
   │                   :443 → SPA + /api/* proxy ─┐ │
   │  backend (uvicorn) 127.0.0.1:8000  ◀─────────┘ │
   │  postgres          127.0.0.1:5432              │
   │  certbot           on demand only              │
   └────────────────────────────────────────────────┘
                │
                ▼
            Gemini API / S3
```

nginx is the only thing the browser talks to. The backend and Postgres ports are bound to `127.0.0.1`, so they are unreachable from outside the instance regardless of security group rules.

## Local Development

```bash
cd infra
docker compose up --build      # open https://localhost (self-signed cert warning is expected)
docker compose down            # add -v to wipe the Postgres volume
```

The `frontend` container serves the production build. For day-to-day frontend work, use `npm run dev` instead (see [frontend.md](frontend.md)).

## Environment Variables

Set these in `infra/.env` (gitignored; copy from `infra/.env.example`). Never put real values in `docker-compose.yml`.

| Variable | Default | Notes |
|---|---|---|
| `JWT_SECRET_KEY` | placeholder | **Set for any real deployment** |
| `POSTGRES_PASSWORD` | `medlens_password` | **Change.** Used for both the DB and the backend `DATABASE_URL` |
| `APP_ENV` | `development` | Set `production`. Also controls log format and dev-only CORS. |
| `GEMINI_API_KEY` | unset | Without it, AI endpoints return 503; the app still starts |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Runtime only; restart the backend to change it |
| `AI_PROVIDER` | `gemini` | `gemini`, `openbiollm`, or `medgemma`. Invalid values fail startup. |
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` | Local providers only. You run Ollama yourself; it isn't in Compose and `host.docker.internal` isn't guaranteed on Linux. |
| `OPENBIOLLM_MODEL`, `MEDGEMMA_MODEL` | see [ai.md](ai.md) | |
| `STORAGE_BACKEND` | `local` | `local` or `s3`. Use `s3` in production; local files are lost when the container is recreated. |
| `AWS_REGION`, `S3_BUCKET_NAME` | unset | Required when `s3` is selected (startup fails otherwise) |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | unset | Local testing only. Production uses an instance IAM role. |
| `APP_VERSION` | `1.0.0` | Reported by `/health` |
| `LOG_LEVEL` | `INFO` | |
| `FRONTEND_PORT` / `FRONTEND_HTTPS_PORT` / `BACKEND_PORT` | `80` / `443` / `8000` | Host ports |
| `DOMAIN` | `medlenshealth.com` | **Build arg.** Baked into `nginx.conf` for the certificate path. |
| `VITE_API_BASE_URL` | `/api` | **Build arg.** Baked into the JS bundle. There is normally no reason to change it. |

Build args require `docker compose build` to take effect. Everything else only needs a container restart.

## Docker Images

- **`backend/Dockerfile`**: multi-stage build that runs as non-root `appuser`. On start it runs `alembic upgrade head` and then `uvicorn --forwarded-allow-ips='*' --no-access-log`.
- **`frontend/Dockerfile`**: multi-stage build (Node build stage, then `nginx:alpine`), with SPA fallback, `/api` proxy, and TLS.
- **`postgres:16`**: stock image.
- **`.dockerignore`** is a security control. It keeps `.env` files and local caches out of image layers.
- Dependencies install in their own layer before the source is copied, using BuildKit cache mounts. CI uses the GitHub Actions cache (`type=gha`).

Both CI workflows end with a `docker build` to prove the images still build. See [design-decisions.md](design-decisions.md), Decisions 18 and 23.

## Compose Runtime Behavior

- `restart: unless-stopped` and healthchecks on all three services. The backend healthcheck parses `/health` and requires `status == "ok"`.
- `backend` waits for `postgres` to be healthy. `frontend` doesn't depend on `backend`; it serves static files, and `/api/*` returns 502 until the backend exists.
- Migrations run automatically on every backend start (a no-op if already current).

## AWS EC2 Runbook

**Prerequisites:** an AWS account, an SSH key pair, and optionally a Gemini API key.

1. **Launch** Ubuntu 22.04 or 24.04 on `t3.small` or larger (`t3.micro` can run out of memory building the frontend), with a 20 GiB disk.
2. **Security group:**

   | Port | Source | Purpose |
   |---|---|---|
   | 22 | Your IP only | SSH |
   | 80 | 0.0.0.0/0 | Redirect to HTTPS and ACME challenge (must stay open for renewals) |
   | 443 | 0.0.0.0/0 | The app |

3. **Install Docker:**
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh && sudo sh get-docker.sh
   sudo usermod -aG docker $USER    # then log out and back in
   ```
4. **Clone:**
   ```bash
   git clone https://github.com/built-by-ann/medlens.git && cd medlens/infra
   ```
5. **Configure:** `cp .env.example .env` and set at least `JWT_SECRET_KEY`, `POSTGRES_PASSWORD`, and `APP_ENV=production`.
6. **Build and start:**
   ```bash
   docker compose build && docker compose up -d
   ```
   The app is now live at `https://<ip>/` using a self-signed placeholder certificate.
7. **Real HTTPS** (once DNS for `DOMAIN` points at the instance):
   ```bash
   docker compose run --rm certbot certonly --webroot -w /var/www/certbot \
     -d medlenshealth.com --email you@example.com --agree-tos --no-eff-email
   docker compose exec frontend nginx -s reload
   ```
   Then add a renewal cron entry:
   ```bash
   0 3,15 * * * cd ~/medlens/infra && docker compose run --rm certbot renew --quiet && docker compose exec frontend nginx -s reload
   ```

**Verify:** `docker compose ps` should show all services healthy. `curl -k https://localhost/api/health` should return `"status":"ok"`. In the browser's network tab, every call should go to `https://<host>/api/...` with no CORS preflights.

### Operations

```bash
# Update (migrations run automatically)
git pull && cd infra && docker compose build && docker compose up -d

# Roll back (code only; does NOT reverse migrations)
git checkout <sha> && cd infra && docker compose build && docker compose up -d

# Logs
docker compose logs -f backend
docker compose logs backend | jq -R 'fromjson? // .'

# Restart one service
docker compose restart backend
```

To undo a migration, run `alembic downgrade` by hand, one step at a time, after backing up the volume.

### Troubleshooting

| Symptom | Fix |
|---|---|
| Out of memory during build | Use a bigger instance or add 2 GB swap |
| `permission denied` on docker | Log out and back in after `usermod` |
| 500 on any DB write | Check backend logs for Alembic errors |
| API calls go to `:8000` or fail CORS | The frontend was built with a non-default `VITE_API_BASE_URL`. Remove it and rebuild. |
| Analyses return 503 "models/... is not found" | Google retired the model. Update `GEMINI_MODEL` and restart the backend. |

## Reverse Proxy and TLS

- `/api/*` has its prefix stripped and is proxied to `backend:8000`. nginx uses Docker's DNS resolver per request, so a recreated backend container keeps working. `client_max_body_size 25m`; forwarded headers are set.
- Because everything is same-origin, production needs no CORS. CORS middleware stays only to allow `localhost` origins when `APP_ENV=development` (for `npm run dev`).
- Port 80 returns a `308` redirect to HTTPS, except for `/.well-known/acme-challenge/`.
- Port 443 uses TLS 1.2/1.3 with Mozilla Intermediate ciphers and HSTS for 6 months (no `includeSubDomains` or `preload`).
- `ensure-dummy-cert.sh` creates a self-signed certificate on first start, so startup never blocks on DNS or Let's Encrypt.
- `certbot` is behind a Compose profile, so it only runs via `docker compose run`.

See [design-decisions.md](design-decisions.md), Decisions 24 and 25.

## S3 File Storage

```bash
aws s3api create-bucket --bucket medlens-documents-<unique> --region us-east-1
aws s3api put-public-access-block --bucket medlens-documents-<unique> \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

Attach an instance IAM role with only these permissions:

```json
{ "Version": "2012-10-17",
  "Statement": [{ "Effect": "Allow",
    "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
    "Resource": "arn:aws:s3:::medlens-documents-<unique>/*" }] }
```

Objects are uploaded with `ACL="private"`, and downloads stream through the API, so no S3 URLs are ever exposed. Credentials are never logged; a test asserts this.

## Logging and Timing

- `APP_ENV=development` logs readable `key=value` lines. Any other value logs one JSON object per line.
- Every response carries `X-Request-ID`, which matches `request_id` on all log lines for that request.
- Log fields pass through an allowlist (`ALLOWED_FIELDS` in `app/core/logging_config.py`). Passwords, tokens, prompts, document text, and AWS credentials are never logged.
- Timing is a `duration_ms` field on existing events, with spans nested by design:

| Event | Covers |
|---|---|
| `http_request_completed` | Whole request |
| `analysis_completed` / `analysis_failed` | AI call plus reconciliation |
| `ai_request_succeeded` / `ai_request_failed` | Provider call only |
| `document_uploaded` | Validation, extraction, storage, and DB write |
| `document_text_extracted` | Parsing only |
| `storage_upload_completed` / `s3_upload_failed` | Storage write only |

## Deferred

| Item | Today |
|---|---|
| DNS pointing at the instance | HTTPS is ready; certbot just needs DNS in place |
| Automated deploys | Manual `git pull` and rebuild over SSH |
| Monitoring and alerting | `/health`, `docker compose ps`, and logs, all checked by hand |
| Backups | Named volume only. Losing the volume loses data, including the keys that point to S3 objects. |
| RDS, load balancing, ECS/Kubernetes | Not needed at single-instance scale |
