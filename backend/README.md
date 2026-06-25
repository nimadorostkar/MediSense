# MediSense Backend — AI Clinical Decision Support

Production FastAPI backend for **MediSense**, an AI clinical decision-support
(CDS) platform for a hospital pilot in China. It turns a doctor's free-text
description of a patient into a **ranked differential diagnosis with reasoning**,
a **safety-screened prescription**, a **live triage queue**, and a
**continuous-learning knowledge base** — using a hybrid AI engine
(vector retrieval + outcome-weighted classifier + a clinical rules/safety layer
evaluated **last**), with optional deep reasoning via **Zhipu GLM**.

> **The single invariant:** the system never auto-commits a clinical decision.
> Every output is a suggestion the licensed physician must confirm. This is
> enforced in code (`requiresPhysicianConfirmation`, server-side commit gates),
> not in comments.

---

## Quick start

### Zero-setup (SQLite, no external services)
```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8787      # creates + seeds SQLite automatically
```
Open interactive docs at **http://localhost:8787/docs**.

### Full stack (Docker: API + Postgres/pgvector + Redis)
```bash
docker compose up -d --build
curl localhost:8787/api/health
curl -X POST localhost:8787/api/clinical -H 'content-type: application/json' \
  -d '{"messages":[{"role":"doctor","text":"67M chest pain radiating to left arm, diaphoretic, HR 118 BP 92/60"}],"lang":"en"}'
```
The second call returns a **red-flag-first** differential (ACS surfaced as a
pinned `Watch`) with version stamps and `requiresPhysicianConfirmation: true`.

### Commands
```bash
make test     # full pytest suite (incl. the safety golden gate)
make check    # ruff + mypy + tests (CI gate)
make smoke    # health + ACS smoke against a running server
```

---

## The safety contract (pipeline order — never reordered)

```
enrich → retrieve → classify → calibrate → apply_rules (LAST, hard veto)
       → rank_and_explain → [optional] Zhipu GLM reason (grounded, re-vetoed)

treatment:  recommend (outcome-weighted) → drug-safety screen (hard veto)
```

- **Rules/safety run last** and can override any statistical output. Allergy
  conflicts hard-block; interactions are graded
  `Contraindicated > Major > Moderate > Minor`; a `Contraindicated` prescription
  cannot be signed without a typed override reason.
- **Do-not-miss surfacing:** red-flag conditions (ACS, sepsis, stroke, PE,
  dissection, DKA, ectopic, meningitis…) are surfaced and pinned `Watch` even at
  low probability; the red-flag banner is raised regardless of rank.
- **Explainable by default:** every suggestion carries supporting/contradicting
  signals, similar-case counts, typical outcomes, and a next-best test.
- **Versioned & audited:** every response stamps `modelVersion`,
  `ruleSetVersion`, `drugRefVersion`; every view/suggestion/override/sign-off is
  written to an immutable, hash-chained audit trail.
- **Degrade gracefully:** a downed classifier / reasoner / drug reference /
  triage scorer yields a labelled, reduced answer — never a blank screen, and
  hard safety blocks still hold.

---

## API surface

| Surface | Endpoints |
|---|---|
| **Chat (v1)** — what the React UI uses | `POST /api/clinical` (probability 0–100, returns `{text: "<json>"}`), `GET /api/health` |
| **Structured (v2)** | `PUT /v2/encounters/{id}/symptoms`, `GET …/differential` (probability 0–1), `POST …/diagnosis`, `POST …/prescription`, `POST /v2/prescriptions/{id}/sign|verify`, `POST /v2/episodes`, `GET /v2/triage/queue`, `POST /v2/encounters/{id}/outcome`, `GET /v2/audit/events` |
| **Ops** | `GET /metrics` (Prometheus), `GET /docs` (OpenAPI) |

The v1 chat shapes match the existing frontend (`src/lib/api.ts`,
`DifferentialCard.tsx`, `TreatmentCard.tsx`) **exactly**, so the current UI works
unchanged. v2 adds idempotency keys, RBAC, and the full clinical workflow.

### Auth & RBAC
- OAuth2/OIDC bearer tokens. `DEV_AUTH=true` accepts a locally-signed dev token
  so the stack runs without the hospital IdP; the real JWKS validation path is
  implemented behind `OIDC_ISSUER`/`OIDC_AUDIENCE`/`OIDC_JWKS_URL`.
- RBAC matrix (spec §4.2) enforced at the boundary: only **Physician** confirms a
  diagnosis / signs an Rx; only **Pharmacist** verifies/holds; audit export is
  **Admin/Safety/IT** only.
- Mint a dev token:
  ```python
  from app.security.oidc import mint_dev_token
  mint_dev_token("p1", "Dr Lin", "physician")   # roles: physician|nurse|pharmacist|admin|safety|it
  ```
- `POST /api/clinical` is intentionally open (read-only suggestion, never a
  commit) so the existing unauthenticated UI keeps working; an authenticated
  actor is recorded when a token is supplied.

---

## Architecture

```
app/
  main.py            FastAPI app, middleware, CORS, lifespan, /metrics
  config.py          pydantic-settings — all env + feature flags
  deps.py            DI: db session, current_user, RBAC guards
  errors.py          standard error envelope (+ degradedMode)
  models.py          SQLAlchemy canonical entities
  schemas.py         Pydantic contracts (v1 chat + v2)
  db/                async engine/session, cross-dialect Embedding type, seed
  engine/            embeddings · vector_index · classify · ood · rules ·
                     drug_safety · recommend · reasoner · labels · triage ·
                     enrich · orchestrator
  ai/                provider.py (interfaces) + zhipu.py (GLM impl)
  integration/       FHIR adapter + canonical mapping + write-back queue
  learning/          data-quality · active-learning · registry/snapshots/eval gates
  security/          oidc · rbac · audit (hash-chain)
  observability/     structured logging · Prometheus metrics
data/                episodes.json · drug_reference.json · code_maps.json
alembic/             async migrations (initial: schema + pgvector + HNSW index)
tests/               rules golden suite · contract · integration · degraded · authz · latency
```

- **DB:** PostgreSQL 16 + pgvector (prod, HNSW ANN) via async SQLAlchemy 2.0 +
  asyncpg; SQLite zero-setup fallback (vector ops degrade to in-process cosine).
- **Migrations:** Alembic owns the schema in prod (no `create_all`); SQLite dev
  materializes tables directly.

---

## Configuration

All config is environment-driven (`.env.example` documents every key). Highlights:

| Var | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://…` (prod) or SQLite (default). Also the data-residency control. |
| `REDIS_URL` | Optional per-encounter cache + pub/sub. |
| `ZHIPU_API_KEY`, `ZHIPU_BASE_URL`, `LLM_CHAT_MODEL`, `EMBEDDING_MODEL`, `LLM_REASONING` | Zhipu GLM reasoning + embeddings. Reasoning is off by default. |
| `DEV_AUTH`, `OIDC_ISSUER`/`OIDC_AUDIENCE`/`OIDC_JWKS_URL` | Auth (dev token vs. hospital IdP). |
| `CORS_ORIGINS`, `RATE_LIMIT_PER_MINUTE` | HTTP boundary. |
| `MODEL_VERSION`, `RULESET_VERSION`, `DRUGREF_VERSION`, `PROMPT_VERSION` | Semantic version stamps on every response. |
| `FHIR_BASE_URL`, `FHIR_WRITE_BACK` | Hospital HIS write-back (mock adapter by default). |

---

## What's real vs. seam-stubbed

**Real:** the API contracts, canonical data model, hybrid pipeline with the
safety-last ordering, calibrated probabilities, OOD detection, drug-safety screen
(allergy/cross-reactivity/interaction/dosing), the full RBAC matrix, OIDC dev +
JWKS path, the immutable hash-chained audit trail, idempotency keys,
continuous-learning capture with the data-quality pipeline, active-learning
queue, KB snapshots + eval-gate runner, bilingual EN/ZH output, triage scoring,
the FHIR canonical mapping + write-back queue, Prometheus metrics, structured
logging, Docker/Compose, Alembic.

**Illustrative / seam-stubbed (clearly isolated):**
- `data/episodes.json` (24 illustrative outcome-labelled episodes) and
  `data/drug_reference.json` — **not real clinical data**; structured for
  replacement by the de-identified 3,000+ Chinese corpus and a licensed China
  formulary, loaded out-of-band.
- Offline embeddings use a deterministic **hashing embedder**; with a Zhipu key
  the real `embedding-3` model is used.
- FHIR transport defaults to a **mock adapter**; the canonical mapping and the
  retried/idempotent write-back queue are real.
- Hospital **IdP** is external — the dev token path runs the stack locally.

See `BUILD_REPORT.md` for test results and how to point at a real Zhipu key and a
hospital FHIR endpoint.
