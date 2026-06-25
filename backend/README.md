# MediSense Backend

FastAPI clinical decision-support engine for the MediSense chat UI. Implements the
pilot **vertical slice**: describe a patient → ranked differential with reasoning →
best-fit diagnosis → screened treatment & prescription.

This is the engine behind `frontend/`. It replaces the old `frontend/server/index.js`
LLM proxy: rankings and drug-safety now come from a real hybrid engine
(retrieval + outcome-weighted classifier + a deterministic rules/safety layer),
not from a single black-box model.

## Why this stack

| Choice | Reason |
|---|---|
| **Python + FastAPI** | The engine is ML (embeddings, retrieval, calibrated classifier, rules). Keeps the API and models in one runtime. Pydantic enforces the clinical contracts; OpenAPI is auto-generated. |
| **PostgreSQL + pgvector** | One ACID datastore for the audit/decision trail *and* vector retrieval at pilot scale — one fewer system to secure for NMPA. Swap to Milvus when episodes pass ~1M (spec §16.3). |
| **SQLite default** | The slice runs with **zero setup**; flip `DATABASE_URL` to Postgres for the production target. |
| **Redis (optional)** | Per-encounter / differential cache (spec §15.3). Not required for the pilot. |

## Quick start (zero setup — SQLite)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                       # optional; defaults work
uvicorn app.main:app --reload --port 8787
```

Then run the frontend (separate terminal):

```bash
cd ../frontend
npm install
npm run dev                                # Vite proxies /api -> http://localhost:8787
```

Open the chat UI, describe a patient, and you get a live differential. Ask
"what should I prescribe?" to get the screened treatment plan.

`GET http://localhost:8787/api/health` confirms the engine is up and how many
episodes are indexed.

### Optional: real LLM narrative polish
Set `ANTHROPIC_API_KEY` in `.env`. The model only *rewrites the prose* — the
rankings and safety flags always come from the engine (spec §12.5/§12.6).

## Production target (Postgres + pgvector + Redis)

```bash
docker compose up -d                       # starts pgvector + redis
# in .env:
DATABASE_URL=postgresql+asyncpg://medisense:medisense@localhost:5432/medisense
uvicorn app.main:app --port 8787
```

The schema is created automatically (pilot). For production use Alembic
migrations and switch the `embedding` JSON column to a native `vector` column
(see "Moving to pgvector" below).

## How a request flows (spec §12.2)

```
symptom text
   → embed (engine/embeddings.py)
   → retrieve k similar episodes (engine/vector_index.py)
   → classify: outcome-weighted vote → calibrated probabilities (engine/classify.py)
   → RULES LAST: red flags + do-not-miss "Watch" pins, hard veto (engine/rules.py)
   → rank & explain  →  (if prescribing) treatment + drug-safety screen
   → response with modelVersion / ruleSetVersion + requiresPhysicianConfirmation
```

The rules/safety layer is evaluated **last** and can override the statistics —
the core safety invariant. Allergy conflicts are a hard block; interactions are
graded Contraindicated > Major > Moderate > Minor.

## API surface

Chat (consumed by the React UI):

| Endpoint | Purpose |
|---|---|
| `POST /api/clinical` | `{messages,lang}` → `{text: "<DiagnosisReply JSON>"}` (differential + optional treatment) |
| `GET /api/health` | engine status, episode count, versions |

Versioned clinical API (spec §17.1):

| Endpoint | Purpose |
|---|---|
| `PUT /v2/encounters/{id}/symptoms` | submit/refine symptoms |
| `GET /v2/encounters/{id}/differential` | ranked differential with evidence (§17.3) |
| `POST /v2/encounters/{id}/diagnosis` | physician confirms (logs a Decision) |
| `POST /v2/encounters/{id}/prescription` | screened treatment & drug suggestions |
| `POST /v2/episodes` | capture an outcome-labelled episode (continuous learning) |
| `GET /v2/triage/queue` | acuity-ranked queue |
| `GET /v2/audit/events` | hash-chained audit trail |

Interactive docs at `http://localhost:8787/docs`.

## Layout

```
app/
  main.py            FastAPI app, CORS, startup seed, optional dist serving
  config.py          env-driven settings
  db.py / models.py  async SQLAlchemy + canonical entities (spec §15.1)
  schemas.py         Pydantic contracts (chat + /v2)
  seed.py            loads seed episodes, builds the retrieval index
  audit_util.py      hash-chained audit writer
  engine/            embeddings · vector_index · classify · rules · recommend ·
                     drug_safety · reasoning · labels · orchestrator
  data/              episodes.json (seed KB) · drug_reference.json
  routers/           clinical · encounters · episodes · triage · audit · health
```

## What's illustrative vs. production-ready

Real now: API contracts, data model, the full hybrid pipeline, drug-safety
screen, audit trail, continuous-learning capture, bilingual output.

Stubbed for the pilot (clear seams to extend): the embedder is a dependency-free
hashing encoder (swap for a clinical sentence encoder), the classifier is an
outcome-weighted k-NN (swap for the GBM/neural ensemble, §12.4), the drug
reference and seed episodes are **illustrative** — replace with a licensed
interaction DB and real (de-identified) episodes, and add OIDC/RBAC auth + FHIR
write-back at the boundary.

### Moving to pgvector
`DiagnosisEpisode.embedding` is a JSON array for portability. On Postgres,
change it to `Vector(256)` (pgvector), add an HNSW index, and replace
`InMemoryVectorIndex.search` with a `ORDER BY embedding <=> :q LIMIT k` query.
Nothing else in the pipeline changes — that's the point of the interface.
