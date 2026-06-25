# MediSense Backend — Build Report

*Production FastAPI CDS backend · built against `MediSense_Production_Specification.md` v2.0 · pilot (China / NMPA).*

This report summarizes what is real vs. seam-stubbed, the verification results,
and how to point the system at a real Zhipu key and a hospital FHIR endpoint.

---

## 1. Final verification results

| Check | Command | Result |
|---|---|---|
| **Full test suite** | `pytest -q` | ✅ **40 passed** |
| **Rules/safety golden suite (hard gate)** | `pytest tests/test_rules_golden.py` | ✅ **17/17 — 100%** |
| Contract tests (v1 chat + v2 shapes) | `pytest tests/test_contract.py` | ✅ 6/6 |
| Integration (learning loop, audit chain, tamper) | `pytest tests/test_integration.py` | ✅ 5/5 |
| Degraded-mode (classifier/reasoner/drugref/triage offline, sparse) | `pytest tests/test_degraded.py` | ✅ 5/5 |
| AuthZ / RBAC | `pytest tests/test_authz.py` | ✅ 6/6 |
| Latency | `pytest tests/test_latency.py` | ✅ p95 well under budget |
| Lint | `ruff check app tests` | ✅ clean |
| Format | `ruff format --check app tests` | ✅ clean |
| Types | `mypy app` | ✅ no issues (49 files) |
| **Docker smoke** | `docker compose up -d` + curl | ✅ health OK, ACS smoke 200 on **Postgres + pgvector ANN** |
| **Audit tamper test** | mutate a row → `verify_chain` | ✅ chain detected broken at the tampered seq |

**Latency** (differential engine, seed KB, hashing embedder, SQLite, this host):
**p50 ≈ 3.9 ms, p95 ≈ 4.4 ms** — far inside the spec §21 budget (p50 < 2 s, p95 < 5 s).
*Method:* 25 sequential `orchestrator.diagnose` calls over 5 representative cases;
percentiles over wall-clock. Real Zhipu embeddings add a network round-trip
(cached per text); the deterministic layers remain sub-second.

### Acceptance smoke (spec §10)
```
GET /api/health → {"ok":true,"episodes":24,"modelVersion":"dx-2026.06.1-pilot",
  "ruleSetVersion":"rules-2026.06.1","drugRefVersion":"drugref-2026.06.1",
  "llmReasoning":false,"datastore":"postgres"}

POST /api/clinical  "67M chest pain radiating to left arm, diaphoretic, HR 118 BP 92/60"
  → redFlag: "RED FLAG: features of acute coronary syndrome — assess now (ECG + troponin)."
    leading: Acute coronary syndrome [Watch, pinned do-not-miss]
    modelVersion/ruleSetVersion stamped · requiresPhysicianConfirmation: true
```

### Safety invariants verified end-to-end
- Penicillin allergy → **Amoxicillin withheld**, **Azithromycin** offered, `Contraindicated` flag.
- Contraindicated Rx **cannot be signed** without a typed override (`409 safety_block`); a valid override is logged + counted + surfaced to the pharmacist.
- Rules layer runs **last**; do-not-miss conditions surface/pin even at low probability; the appendicitis rule does **not** false-fire on right-sided *chest* pain (precision test).
- RBAC: nurse cannot confirm a diagnosis; pharmacist cannot sign; physician cannot export audit (all `403`).
- Idempotency: a repeated `diagnosis`/`sign`/`episodes` call with the same key replays the stored result.
- Audit hash-chain verifies and is tamper-evident.

---

## 2. What is REAL

- **API contracts** — v1 chat (probability 0–100, `{text}` envelope) matching the
  existing React UI exactly; v2 structured flow (probability 0–1) with idempotency
  keys, RBAC scoping, and a standard error envelope with `degradedMode`.
- **Canonical data model** (spec §5) — all entities as async SQLAlchemy models with
  UUID PKs and timestamps; cross-dialect `Embedding` column (pgvector on Postgres,
  JSON on SQLite).
- **Hybrid engine** with the non-negotiable ordering
  `retrieve → classify → calibrate → rules (last) → explain`, OOD detection,
  evidence-strength calibration (honest, not overconfident), and an
  outcome-weighted treatment recommender.
- **Drug-safety screen** — allergy + class cross-reactivity, drug–drug
  interactions (graded severity), and pediatric/geriatric/renal dosing bounds,
  with hard contraindication blocks + safer-alternative substitution.
- **Security** — OIDC dev-token path + real JWKS validation seam; full RBAC matrix;
  immutable, hash-chained (`prev_hash`/`hash`) audit trail with sequence numbers.
- **Continuous learning** — episode capture with the automated data-quality
  pipeline (schema/outlier/code-map checks + de-identification + quarantine),
  active-learning queue (overrides + OOD routed for review), KB snapshot hashing,
  model registry + runtime eval-gate runner.
- **Integration** — FHIR canonical mapping (`Condition`, `MedicationRequest`) and an
  idempotent, retried write-back path with a `queued`/`written` status surfaced to
  the clinician (never silently dropped).
- **Triage** — transparent, rule-weighted acuity scoring with Critical/Urgent/Routine
  bands and a degraded manual-order mode.
- **Ops** — structured JSON logging with correlation IDs, Prometheus `/metrics`,
  rate limiting, multi-stage non-root Docker image with healthcheck,
  docker-compose (api + postgres/pgvector + redis), Alembic migrations
  (schema + pgvector extension + HNSW index).
- **Bilingual** EN/ZH output driven by `lang` + the code-map terminology service.

## 3. What is SEAM-STUBBED (clearly isolated, ready to swap)

| Seam | Current state | To productionize |
|---|---|---|
| **Knowledge base** | `data/episodes.json` — 24 *illustrative*, clinician-shaped, de-identified episodes | Load the de-identified/licensed 3,000+ Chinese corpus out-of-band (same schema; `POST /v2/episodes` or a bulk loader). |
| **Drug reference** | `data/drug_reference.json` — illustrative interactions/allergy/dosing | Replace with a licensed China formulary + interaction DB; bump `DRUGREF_VERSION`. |
| **Embeddings (offline)** | Deterministic hashing embedder when no key | Set `ZHIPU_API_KEY` → real `embedding-3`. |
| **LLM reasoning** | Off by default (deterministic pipeline answers) | Set `ZHIPU_API_KEY` + `LLM_REASONING=true` → grounded, citation-required GLM layer (rules re-veto downstream). |
| **Hospital IdP** | `DEV_AUTH=true` local signed token | Set `DEV_AUTH=false` + `OIDC_ISSUER`/`OIDC_AUDIENCE`/`OIDC_JWKS_URL`. |
| **FHIR transport** | Mock adapter (mapping + write-back queue are real) | Set `FHIR_BASE_URL` + `FHIR_WRITE_BACK=true`. |
| **Model training** | Calibrated k-NN + eval-gate runner | Train a GBM/neural ensemble offline against a hash-identified KB snapshot; the registry/version-stamp/eval-gate plumbing already exists. |

---

## 4. Pointing at the real Zhipu key + hospital FHIR

```bash
# .env
ZHIPU_API_KEY=sk-...                       # enables real embedding-3 retrieval
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4
LLM_CHAT_MODEL=glm-4.6                      # verify current id against Zhipu docs
EMBEDDING_MODEL=embedding-3
LLM_REASONING=true                          # turn on grounded GLM reasoning

DEV_AUTH=false                              # use the hospital IdP
OIDC_ISSUER=https://idp.hospital.example/realms/medisense
OIDC_AUDIENCE=medisense
OIDC_JWKS_URL=https://idp.hospital.example/realms/medisense/protocol/openid-connect/certs

FHIR_BASE_URL=https://his.hospital.example/fhir
FHIR_WRITE_BACK=true

DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/medisense   # also the residency control
```
> **Model identifiers are config-driven.** Defaults reflect the pilot build
> (GLM `glm-4.6`, `embedding-3`); verify against Zhipu's current docs and update
> the env if they changed. The provider is isolated behind `app/ai/provider.py`,
> so swapping the model — or the whole LLM — is configuration, not code.

---

## 5. Known limitations & notes

- The **offline hashing embedder** is intentionally crude (bag-of-features); on
  the 24-episode seed KB it produces sensible neighbours and an honest,
  conservatively-calibrated (often `Low`) confidence. Real `embedding-3` +
  the full corpus yield the spec's higher, well-separated probabilities.
- The **audit hash-chain** serializes writes within a transaction; under
  multi-writer Postgres the `seq`/`hash` uniqueness constraints catch any race
  (the loser retries). Seeding is made concurrency-safe across Gunicorn workers
  via a Postgres transaction-level advisory lock.
- **Roadmap seams** (RAG specialty routing, multimodal, shadow/canary promotion)
  are architected and flagged off per spec §2.3 / §12.5, not part of go-live.
- This build uses **illustrative clinical data**; no real patient data is
  included. All clinical examples are for demonstration and always presented for
  physician confirmation.

*MediSense backend · production build · clinical decision support (non-autonomous) · all outputs require physician sign-off.*
