# Roadmap

This roadmap tracks MedLens's development milestones across five sprints, from backend foundation through model evaluation. See `README.md`'s own Roadmap section for a condensed version, and `docs/PRD.md` for the original scope this roadmap implements.

---

## Sprint 1: Backend Foundation (Completed)

- FastAPI backend
- Docker and Docker Compose
- PostgreSQL
- SQLAlchemy and Alembic
- JWT authentication (registration and login)
- `/users/me`
- Health endpoint
- Backend testing foundation

---

## Sprint 2: AI Analysis Backend (Completed)

- Clinical document CRUD
- Medication CRUD
- TXT/PDF/CSV upload
- AI provider architecture and Gemini integration
- Prompt templates and structured extraction
- Deterministic reconciliation engine
- Analysis persistence, retrieval, and deletion
- Comprehensive backend testing

---

## Sprint 3: Frontend Application (Completed)

- React frontend foundation (project setup, routing, layout, API client, authentication foundation); see `docs/frontend.md`
- Dashboard, patient management, and document management
- Analysis history and detail views
- The full medication reconciliation resolution workflow
- Account settings (profile, appearance, accessibility)
- Responsive UI
- Frontend testing

---

## Sprint 4: Production Engineering (In Progress)

- AWS EC2 deployment via Docker Compose: done, see `docs/deployment.md`
- CI/CD (automated backend and frontend checks, plus Docker image build validation): done
- Reverse proxy and HTTPS/TLS: done
- Production monitoring and alerting: planned
- Performance optimization: planned
- Automated (CI-triggered) deployment: planned

---

## Sprint 5: Model Evaluation (In Progress)

- Synthetic benchmark dataset: completed
- OpenBioLLM integration: completed (selectable via `AI_PROVIDER=openbiollm`; switched from Hugging Face's hosted Inference Providers to local Ollama inference before scoring, after the hosted path proved operationally unreliable during pre-evaluation smoke testing - see `docs/ai.md`)
- MedGemma integration: completed (selectable via `AI_PROVIDER=medgemma`; same local-Ollama switch as OpenBioLLM, and moved from a 27B to a locally-runnable 4B checkpoint at the same time)
- Evaluation runner: completed (`python -m benchmark.runner`; records structured predictions/results per provider)
- Evaluation metrics: completed (`python -m benchmark.metrics`; medication-detection precision/recall/F1, attribute accuracy, reliability, and latency per provider, computes no ranking yet; see `benchmark/README.md`)
- Multi-model comparison report: planned

---

## Long-Term Ideas

- Background jobs
- Search across analyses
- PDF/CSV/JSON export
- Cloud storage improvements (backups, managed PostgreSQL)
- Kubernetes, if the project ever genuinely outgrows a single instance
