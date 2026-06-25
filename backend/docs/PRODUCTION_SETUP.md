# MediSense — Production Setup: AI, Data & Deployment

A practical, end-to-end guide for taking MediSense from the seed/demo state to a
real deployment. Three parts:

1. [Add AI](#1-add-ai-zhipu-glm) — wire up Zhipu GLM reasoning + embeddings.
2. [Add data](#2-add-data--symptoms--previous-diagnoses) — load your own disease
   symptoms and previous diagnoses (the knowledge base).
3. [Run as production](#3-run-as-production) — production config, secrets,
   migrations, deployment.

> **Mental model.** MediSense learns from **episodes**:
> `symptoms → diagnosis → treatment → recovery outcome`. For each new patient it
> embeds the symptom text, retrieves the most similar past episodes, weights them
> by what actually worked, runs the safety/rules layer **last**, and returns a
> ranked differential. **More good episodes → better suggestions.** The AI layer
> (Zhipu) makes retrieval semantic and adds grounded reasoning on top.

---

## 1. Add AI (Zhipu GLM)

MediSense runs fully **without** AI (deterministic hashing embedder + rules). A
Zhipu key upgrades two things:

- **Embeddings** → real `embedding-3` vectors (far better semantic retrieval).
- **Reasoning** → a grounded, citation-required **GLM** summary layer (rules
  still run last and can veto it).

### 1.1 Get a key
Sign up at **https://open.bigmodel.cn/** (Zhipu / BigModel) and create an API key.

### 1.2 Configure (`backend/.env`)
```bash
ZHIPU_API_KEY=your-key-here
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4   # China; intl endpoint swappable
LLM_CHAT_MODEL=glm-4.6          # verify current id against Zhipu docs
EMBEDDING_MODEL=embedding-3
LLM_REASONING=true              # turn ON grounded GLM reasoning
LLM_MAX_TOKENS=1024             # bounded cost per call
LLM_TIMEOUT_SECONDS=12
```
| Setting | Effect |
|---|---|
| `ZHIPU_API_KEY` only | Real `embedding-3` retrieval; no generated text. |
| `ZHIPU_API_KEY` + `LLM_REASONING=true` | Embeddings **and** grounded GLM summary. |
| no key | Fully offline (hashing embedder, deterministic). |

### 1.3 Verify
```bash
curl localhost:8787/api/health      # → "llmReasoning": true  when key + reasoning on
```

> **Resilience & safety (built in):** every LLM claim must cite a retrieved
> episode or it is suppressed; the rules/safety layer re-vetoes LLM output;
> timeouts + retries fall back to the deterministic pipeline ("degraded mode —
> reasoner offline") so a Zhipu outage never blocks a response. Details:
> [`AI_SETUP.md`](./AI_SETUP.md).

> ⚠️ **Re-embed after changing `EMBEDDING_MODEL`.** Stored episode vectors must
> live in the same space as query vectors — see [§2.5](#25-re-embedding--reseeding).

---

## 2. Add data — symptoms & previous diagnoses

The knowledge base lives in three files under `backend/data/` (all *illustrative*
seed data, made to be replaced):

| File | Holds |
|---|---|
| `episodes.json` | **Previous diagnoses**: symptoms → diagnosis → treatment → outcome (the learning unit). |
| `code_maps.json` | Condition → ICD + Chinese label + red-flag marker; drug EN/ZH labels. |
| `drug_reference.json` | Interactions, allergy cross-reactivity, dosing bounds (drug safety). |

### 2.1 The episode shape (a previous diagnosis)
Each entry in `episodes.json → episodes[]`:
```json
{
  "symptomText": "58F crushing chest pressure, breathless, sweating, radiating to jaw, diabetic",
  "diagnosis": "Acute coronary syndrome",
  "icd": "I21.9",
  "outcome": 0.84,                       // 0..1 recovery signal — REQUIRED, what "worked"
  "nextBestTest": "12-lead ECG and troponin",
  "supporting": ["chest pressure", "dyspnea", "jaw radiation", "diabetes"],
  "treatment": {
    "plan": ["ECG + serial troponin", "Aspirin 300mg", "Urgent cardiology"],
    "medications": [
      { "drug": "Aspirin", "dose": "300 mg", "route": "PO", "frequency": "once", "duration": "once" }
    ]
  }
}
```
- `symptomText` is what gets embedded for retrieval — write it the way clinicians describe cases.
- `outcome` (0–1) is the secret ingredient: it weights plans that actually led to recovery.
- `supporting[]` powers the evidence drawer (matching symptoms).

### 2.2 Three ways to add data

**A) Edit the seed file** (loaded on first start, when the KB is empty)
```bash
# 1. add entries to backend/data/episodes.json → episodes[]
# 2. reseed (SQLite):
cd backend && rm -f medisense.db && uvicorn app.main:app --port 8787
```

**B) Add live via the API** (embeds + indexes immediately — no restart, works on a
populated Postgres). Requires a Physician/Safety/Admin token.
```bash
TOKEN=$(cd backend && . .venv/bin/activate && \
  python -c "from app.security.oidc import mint_dev_token as m; print(m('p1','Dr Lin','physician'))")

curl -X POST localhost:8787/v2/episodes \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{
    "symptomText": "30F sudden severe headache, neck stiffness, photophobia, fever",
    "diagnosis": "Meningitis", "icd": "G03.9", "outcome": 0.85,
    "nextBestTest": "Lumbar puncture",
    "treatment": {"plan": ["Urgent LP","Empirical antibiotics"], "medications": [
      {"drug":"Ceftriaxone","dose":"2 g","route":"IV","frequency":"twice daily","duration":"7 days"}
    ]}
  }'
```
Each submission passes the **automated data-quality pipeline** (schema +
outlier/label checks + de-identification + code-map verification). Bad data is
**quarantined → HTTP 422**, never silently admitted.

**C) Bulk-load your corpus** (out-of-band). The format scales to the 3,000+
episode corpus. Either point `episodes.json` at your de-identified export (same
shape) and reseed an empty DB, or loop `POST /v2/episodes` from a script:
```bash
jq -c '.episodes[]' my_corpus.json | while read -r ep; do
  curl -s -X POST localhost:8787/v2/episodes -H "authorization: Bearer $TOKEN" \
       -H 'content-type: application/json' -d "$ep" >/dev/null
done
```

### 2.3 Register new conditions & drugs
When you add episodes with **new conditions or drugs**, also update the maps so
labels, ICD codes, and safety screening cover them:

`data/code_maps.json` → `conditions`:
```json
"Meningitis": { "icd": "G03.9", "zh": "脑膜炎", "redFlag": true }
```
`data/code_maps.json` → `drugs`: `"Ceftriaxone": "头孢曲松"`.

`data/drug_reference.json` → `drugs` (for interaction/allergy/dosing screening):
```json
"ceftriaxone": { "classes": ["cephalosporin","beta-lactam","antibiotic"] }
```
plus any `interactions`, `allergy_cross_reactivity`, or `dosing_bounds` entries.

### 2.4 Red-flag (do-not-miss) detection
Surfacing a time-critical condition **even at low probability** is driven by the
versioned rule set in `app/engine/rules.py` (`RED_FLAG_RULES`). To make MediSense
recognise a new do-not-miss presentation, add a `RedFlagRule` there (keyword
groups + optional vitals predicate + EN/ZH banner) and bump `RULESET_VERSION`.
Add a golden test in `tests/test_rules_golden.py` (the suite is a 100% gate).

### 2.5 Re-embedding / reseeding
- **Seeding only runs when the KB is empty** (guarded by a Postgres advisory lock
  across workers). To reseed from the file: SQLite → delete `medisense.db`;
  Postgres → `docker compose down -v` (wipes the volume). To *add* to a populated
  DB without wiping, use method **B/C** above.
- **Changing `EMBEDDING_MODEL` invalidates stored vectors** — re-embed the whole
  KB (reseed, or re-`POST` episodes) so query and episode vectors match.

---

## 3. Run as production

### 3.1 Backend env (`backend/.env`)
```bash
# Datastore — Postgres + pgvector (also the data-residency control)
DATABASE_URL=postgresql+asyncpg://medisense:STRONGPASS@db-host:5432/medisense
REDIS_URL=redis://redis-host:6379/0
DATA_REGION=cn-pilot

# Auth — turn OFF dev tokens, use the hospital IdP (OIDC)
DEV_AUTH=false
OIDC_ISSUER=https://idp.hospital.example/realms/medisense
OIDC_AUDIENCE=medisense
OIDC_JWKS_URL=https://idp.hospital.example/realms/medisense/protocol/openid-connect/certs

# AI (optional but recommended) — see §1
ZHIPU_API_KEY=...
LLM_REASONING=true

# HTTP — allow only the real frontend origin(s)
CORS_ORIGINS=https://app.medisense.example
RATE_LIMIT_PER_MINUTE=120

# Version stamps (semantic; stamped on every response & audit record)
MODEL_VERSION=dx-2026.06.1-pilot
RULESET_VERSION=rules-2026.06.1
DRUGREF_VERSION=drugref-2026.06.1

# Integration — real HIS write-back (mapping + queue already implemented)
FHIR_BASE_URL=https://his.hospital.example/fhir
FHIR_WRITE_BACK=true
```
> **Secrets** come from the environment / a secret manager — never commit them.
> `DATABASE_URL` controls data residency (keep it in the permitted region).

### 3.2 Frontend env (`frontend/.env`) — point the UI at the backend
A built bundle has **no dev proxy**. Either:

- **Same-origin (recommended):** serve `dist/` and proxy `/api` + `/v2` to the
  backend with one reverse proxy; leave `VITE_API_URL` unset.
  ```nginx
  location /api/ { proxy_pass http://backend:8787; }
  location /v2/  { proxy_pass http://backend:8787; }
  location /     { root /usr/share/nginx/html; try_files $uri /index.html; }
  ```
- **Separate domain:** set the absolute URL and allow it in backend CORS.
  ```bash
  VITE_API_URL=https://api.medisense.example/api/clinical
  # backend: CORS_ORIGINS=https://app.medisense.example
  ```
Then `cd frontend && npm run build` and deploy `dist/`.

> The offline demo stub is **off in production** — a failed engine call shows an
> explicit error, never fabricated clinical data. (Do not set
> `VITE_ALLOW_OFFLINE_STUB`.)

### 3.3 Bring it up (Docker)
```bash
cd backend
docker compose up -d --build      # api (gunicorn+uvicorn workers) + postgres/pgvector + redis
```
On Postgres the container entrypoint runs **Alembic migrations** (schema +
pgvector extension + HNSW index) before serving; the KB seeds once on first
start. Tune workers with `WEB_CONCURRENCY` (compose env).

Apply migrations manually if deploying the API elsewhere:
```bash
alembic upgrade head
```

### 3.4 Operations
- **Health / readiness:** `GET /api/health` (used by the container healthcheck).
- **Metrics:** `GET /metrics` (Prometheus) — latency, suggestions, safety blocks,
  contraindication overrides, degraded-mode counters.
- **Audit:** immutable hash-chained trail; export via `GET /v2/audit/events`
  (Admin/Safety/IT only); `chainValid` flags tampering.
- **Logs:** structured JSON with correlation IDs.

### 3.5 Go-live checklist
- [ ] `DATABASE_URL` → Postgres + pgvector, in the permitted region; backups on.
- [ ] `DEV_AUTH=false` and OIDC issuer/audience/JWKS configured.
- [ ] `CORS_ORIGINS` restricted to the real frontend origin(s); HTTPS/TLS everywhere.
- [ ] Real KB loaded (de-identified episodes) and `code_maps` / `drug_reference`
      updated; licensed formulary in place; `DRUGREF_VERSION` bumped.
- [ ] `ZHIPU_API_KEY` set if using AI; KB re-embedded for the chosen model.
- [ ] `alembic upgrade head` applied; seed verified (`/api/health` episode count).
- [ ] Frontend built with the correct `VITE_API_URL` / same-origin proxy; stub off.
- [ ] Golden safety suite green (`make test`); smoke test passes (`make smoke`).
- [ ] Secrets from a secret manager; `/metrics` scraped; audit export tested.

---

**See also:** [`AI_SETUP.md`](./AI_SETUP.md) · [`GUIDE.md`](./GUIDE.md) ·
[`README.md`](./README.md) · [`BUILD_REPORT.md`](./BUILD_REPORT.md) ·
[`../../docs/API_AND_INTEGRATION.md`](../../docs/API_AND_INTEGRATION.md)
