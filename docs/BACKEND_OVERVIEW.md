# MediSense Backend — Overview

A FastAPI clinical engine behind the chat UI: describe a patient → ranked
differential with reasoning → best-fit diagnosis → screened prescription.

## Stack
- **FastAPI (Python)** — engine + API in one runtime; Pydantic-enforced contracts.
- **PostgreSQL + pgvector** (production) / **SQLite** (zero-setup default).
- **Redis** — optional per-encounter cache.

## How it works (rules evaluated last, hard veto)
```
symptoms → embed → retrieve similar episodes → outcome-weighted classifier
→ calibrate → rules/safety (red flags + do-not-miss) → differential / treatment
```
Every response stamps `modelVersion` / `ruleSetVersion` and
`requiresPhysicianConfirmation`. Allergy conflicts hard-block; interactions
graded Contraindicated > Major > Moderate > Minor.

## Key endpoints
- `POST /api/clinical` — chat: returns differential (+ treatment when prescribing).
- `GET /api/health` — engine status & versions.
- `PUT/GET/POST /v2/encounters/{id}/symptoms|differential|diagnosis|prescription`
- `POST /v2/episodes` · `GET /v2/triage/queue` · `GET /v2/audit/events`

## Run
```bash
cd backend && pip install -r requirements.txt
uvicorn app.main:app --port 8787      # SQLite, no setup
# Postgres: docker compose up -d, then set DATABASE_URL
```

## Layout
`app/main.py` app · `engine/` (embeddings, retrieval, classify, rules,
drug_safety, recommend, orchestrator) · `routers/` · `data/` seed episodes +
drug reference · `models.py`/`schemas.py` canonical data + contracts.

## Real vs. illustrative
Real: contracts, data model, hybrid pipeline, drug-safety screen, audit trail,
continuous-learning capture, bilingual output.
Stubbed seams: hashing embedder, k-NN classifier, sample drug/episode data,
auth (OIDC/RBAC) and FHIR write-back.
