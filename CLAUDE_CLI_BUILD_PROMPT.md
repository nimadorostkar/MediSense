# MediSense Backend — Claude CLI Implementation Prompt

> Paste everything below the line into Claude CLI (e.g. `claude` in an empty `backend/` directory, or reference this file). It is written as a single, self-contained build brief. Work through it phase by phase, committing after each phase. Ask before deviating from any **MUST** requirement.

---

## 0. Role and mission

You are a senior backend engineer building the **production** backend for **MediSense**, an AI clinical decision-support (CDS) platform for a hospital pilot in **China**. The backend is a **FastAPI** service, containerized with **Docker**, backed by **PostgreSQL + pgvector**, that powers an existing **React AI-chat UI**. It turns a doctor's free-text description of a patient and symptoms into a **ranked differential diagnosis with reasoning**, a **safety-screened prescription**, a **live triage queue**, and a **continuous-learning knowledge base** — using a **hybrid AI engine** (vector retrieval + outcome-weighted classifier + a clinical rules/safety layer evaluated **last**), with deep reasoning powered by **Zhipu GLM** (a Chinese LLM) and **Zhipu embeddings** for the RAG knowledge base.

This is a **clinical decision-support** product, not an autonomous doctor. The single most important invariant: **the system never auto-commits a clinical decision. Every output is a suggestion the licensed physician must confirm.** Encode this in code, not comments.

Build it to be **buildable, runnable, tested, and auditable**. Prefer correctness, clarity, and safety over cleverness. Do not stub anything you can implement properly; clearly mark and isolate the few seams that genuinely require external systems (hospital HIS, hospital identity provider).

---

## 1. Non-negotiable invariants (enforce in code)

1. **Human-in-the-loop, always.** No diagnosis is recorded and no prescription is issued/written-back without an explicit, authenticated physician confirmation/sign-off event. Every suggestion payload carries `requiresPhysicianConfirmation: true`, enforced **server-side** on commit.
2. **Rules/safety layer runs LAST and has hard veto.** Pipeline order is the safety contract: `retrieve → classify → calibrate → rules/safety`. A hard safety rule (allergy match, contraindication, dosing limit, red-flag) can override any statistical output. Never evaluate rules before classification.
3. **Nothing unsafe reaches the doctor unflagged.** A drug that fails a hard rule is withheld or surfaced with an explicit severe banner + a safer alternative. Allergy conflicts hard-block. Interaction severity is graded `Contraindicated > Major > Moderate > Minor`; `Contraindicated` is a hard block requiring a typed override reason.
4. **Explainable by default.** No suggestion may be emitted without machine-readable evidence references (supporting symptoms, contradicting signals, count + identity of similar cases, typical outcomes, next-best test). The API must not return a suggestion lacking them.
5. **Everything is versioned and stamped.** Every response stamps `modelVersion`, `ruleSetVersion`, and (for Rx) `drugRefVersion`. Models, rule sets, drug references, and prompts carry semantic versions.
6. **Auditability.** Every view, suggestion, override, and sign-off is written to an **immutable, hash-chained** audit trail (`prev_hash`/`hash`), traceable to the exact versions that produced it.
7. **Fail safe, degrade gracefully.** On low confidence / missing data / a downed dependency, return a labelled degraded answer with a clear caveat — never a confident guess and never a blank screen. Hard safety blocks must still hold in degraded mode.
8. **Privacy by design.** De-identify data used for learning; minimize PII in payloads and logs; make data residency configurable. Secrets come from the environment, never from code.

---

## 2. Tech stack (MUST)

- **Language/runtime:** Python 3.12, **FastAPI**, **Uvicorn** (Gunicorn+Uvicorn workers in prod).
- **Validation/contracts:** **Pydantic v2** models for every request/response.
- **DB:** **PostgreSQL 16 + pgvector** (production) via **async SQLAlchemy 2.0** + **asyncpg**; **SQLite** fallback for zero-setup local dev (vector ops degrade to in-process cosine when pgvector is absent).
- **Migrations:** **Alembic** (autogenerate + reviewed migrations; no `create_all` in prod).
- **Cache / events:** **Redis** (optional per-encounter context cache + pub/sub for near-real-time vitals/triage updates).
- **AI provider:** **Zhipu GLM** for reasoning, **Zhipu embeddings** for retrieval — behind a provider interface so the model is swappable by config (see §6).
- **Auth:** **OAuth2 / OIDC** bearer tokens + **RBAC**; JWT validation middleware. The hospital IdP is external — provide a working local dev issuer/dev-token path plus the real OIDC validation seam.
- **Testing:** **pytest** + **pytest-asyncio** + **httpx** AsyncClient; coverage gate on safety-critical modules.
- **Quality:** **ruff** (lint+format), **mypy** (typed), pre-commit config.
- **Packaging/deploy:** **Docker** + **docker-compose** (api, postgres+pgvector, redis); multi-stage image; healthchecks; `.env.example`.
- **Observability:** structured JSON logging with correlation IDs, Prometheus `/metrics`, OpenTelemetry-ready tracing hooks.

Do **not** introduce a different web framework, ORM, or DB. Keep dependencies lean and pinned.

---

## 3. What to build (full production scope, phased)

Build the complete surface below. Ship in phases, each independently runnable and tested. Use feature flags (env-driven) for roadmap seams so they are wired but off by default.

### Pillars
- **Diagnose** — ranked differential with calibrated probabilities, confidence bands, evidence, red flags, OOD detection, next-best-test.
- **Prescribe** — outcome-weighted treatment + medications, each passed through the real-time safety screen.
- **Triage** — live acuity-scored, ordered patient queue with Critical/Urgent/Routine bands and escalation alerts.
- **Integrate** — FHIR/HL7 adapter seam to read patient context and write back signed decisions (transactional, idempotent, reconciled). Pilot may run against a FHIR sandbox / mock adapter; the canonical-model mapping and write-back queue MUST be real.

### Cross-cutting
- Continuous-learning loop (episode capture → validate/de-identify → embed → live-index), with an automated **data-quality pipeline** (schema validation, de-dup, outlier/label-consistency checks, code-map verification, de-identification, quarantine of bad data).
- **Active learning**: physician overrides and high-uncertainty/OOD cases routed to a review queue as priority training signal.
- **MLOps seams**: immutable KB snapshots (hash-identified), model registry with version stamps, offline eval gates (Top-1/Top-3 accuracy, calibration error, subgroup/fairness, safety golden suite, latency), shadow-mode hook. Implement the registry, snapshotting, and eval-gate runner; the heavy model training can be a documented, reproducible script.
- **Bilingual** output (Chinese / English) driven by a `lang` field and a terminology/labels service.
- **RBAC** per the matrix in §8, enforced at the API boundary.

---

## 4. API contract — MUST match the existing frontend exactly

The existing React UI (`src/lib/api.ts`, `DifferentialCard.tsx`, `TreatmentCard.tsx`) already consumes the contract below. **Honor these shapes exactly** so the current frontend works unchanged. You may add new optional fields/endpoints, but must not break the existing ones.

Dev base URL: `http://localhost:8787`. Interactive docs at `/docs`. CORS configurable via `CORS_ORIGINS`.

### 4.1 Chat surface (primary — what the UI uses today)

**`POST /api/clinical`** — runs the engine over a conversation, returns the structured reply the chat renders.

Request (also accept legacy `{ "prompt": "...", "lang": "en" }`):
```json
{
  "messages": [
    { "role": "doctor", "text": "62F, 3 days fever, productive cough, right-sided pleuritic chest pain. RR 22, SpO2 94%." }
  ],
  "lang": "en"
}
```
- `role` is `doctor` or `ai`; only `doctor` turns form the clinical case.
- A prescriptive turn (e.g. *"what should I prescribe?"*) MUST also produce a `treatment` block.
- Best-effort parse age/sex/allergies/current-meds/vitals/negatives from free text; prefer structured fields when present.

Response is `{ "text": "<JSON string>" }` where `text` parses to (**`probability` here is 0–100**):
```json
{
  "redFlag": "",
  "summary": "Based on 2 similar past case(s), the leading consideration is Community-acquired pneumonia (~48%).",
  "differential": [
    { "condition": "Community-acquired pneumonia", "icd": "J18.9",
      "probability": 48.2, "confidence": "Moderate",
      "because": "2 similar case(s); ~92% improved on the matched plan" }
  ],
  "nextBestTest": "Chest X-ray",
  "treatment": null,
  "modelVersion": "dx-2026.06.1-pilot",
  "ruleSetVersion": "rules-2026.06.1",
  "requiresPhysicianConfirmation": true
}
```
When the doctor asks to treat, `treatment` is:
```json
{
  "bestDiagnosis": "Community-acquired pneumonia", "icd": "J18.9",
  "rationale": "Drawn from past cases confirmed as ... with good recovery; passed the drug-safety screen.",
  "plan": ["Confirm with chest X-ray", "Assess CURB-65 severity", "Oral antibiotics if low risk, review at 48h"],
  "medications": [
    { "drug": "Amoxicillin", "dose": "500 mg", "route": "PO", "frequency": "three times daily", "duration": "5 days", "note": "" }
  ],
  "safety": [ { "severity": "Contraindicated", "message": "Amoxicillin conflicts with documented penicillin allergy — ..." } ],
  "monitoring": "Re-assess in 48h; return if SpO2 falls.",
  "requiresPhysicianConfirmation": true
}
```
Confidence band enum (UI normalizes): `High | Moderate | Low | Watch` (`Watch` = pinned do-not-miss).

**`GET /api/health`**
```json
{ "ok": true, "episodes": 24, "modelVersion": "dx-2026.06.1-pilot",
  "ruleSetVersion": "rules-2026.06.1", "drugRefVersion": "drugref-2026.06.1",
  "llmReasoning": true, "datastore": "postgres" }
```

### 4.2 Versioned clinical API (`/v2`) — structured flow (**`probability` here is 0–1**)

| Method & path | Body → Response |
|---|---|
| `PUT /v2/encounters/{id}/symptoms` | `SymptomSubmission` → `{encounterId, ok}` |
| `GET /v2/encounters/{id}/differential` | – → `DifferentialResponse` |
| `POST /v2/encounters/{id}/diagnosis` | `DiagnosisConfirmation` → `{encounterId, confirmed, logged}` |
| `POST /v2/encounters/{id}/prescription` | `PrescriptionRequest` → `PrescriptionResponse` |
| `POST /v2/prescriptions/{id}/sign` | physician sign → triggers HIS write-back (idempotent) |
| `POST /v2/prescriptions/{id}/verify` | pharmacist verify / hold |
| `POST /v2/episodes` | `EpisodeIn` → `{episodeId, indexed}` (embeds + live-indexes) |
| `GET /v2/triage/queue?limit=20` | – → `{queue:[…]}` |
| `POST /v2/encounters/{id}/outcome` | structured recovery outcome → updates KB |
| `GET /v2/audit/events?limit=50` | – → `{events:[…]}` (RBAC-scoped) |

Representative shapes:

`SymptomSubmission`
```json
{ "symptomText": "24yo asthmatic, wheeze, breathless, cough", "age": 24, "sex": "M",
  "vitals": {"spo2": 93, "hr": 96}, "allergies": [], "medications": [], "lang": "en" }
```
`DifferentialResponse` item + top-level `redFlags[]`, `ood`, `modelVersion`, `ruleSetVersion`, `requiresPhysicianConfirmation`:
```json
{ "condition": "Acute asthma exacerbation", "icd": "J45.901", "probability": 0.62,
  "confidence": "High", "supporting": [], "contradicting": [], "similarCases": 2,
  "typicalOutcomes": {"improved": 0.89, "readmission_30d": 0.0}, "nextBestTest": "Peak expiratory flow",
  "counterfactual": {"remove": "wheeze", "newProbability": 0.41} }
```
`DiagnosisConfirmation` (logs a `Decision` + audit event):
```json
{ "condition": "Acute asthma exacerbation", "icd": "J45.901",
  "overridden": false, "overrideReason": null, "physician": "Dr Lin" }
```
`PrescriptionRequest` → `PrescriptionResponse {encounterId, drugRefVersion, ruleSetVersion, treatment}`:
```json
{ "condition": "Acute asthma exacerbation", "allergies": ["penicillin"], "currentMedications": ["warfarin"], "lang": "en" }
```
`EpisodeIn` (continuous-learning unit):
```json
{ "symptomText": "...", "diagnosis": "Influenza", "icd": "J11.1",
  "treatment": {"plan": [], "medications": []}, "outcome": 0.93, "nextBestTest": "PCR" }
```

### 4.3 API conventions (production)
- Versioned (`/v2/...`), JSON over HTTPS, OAuth2/OIDC bearer tokens, RBAC-scoped.
- **Idempotency keys** on all write endpoints (`sign`, `diagnosis`, `episodes`, write-back) so retries are safe.
- Standard error envelope with machine-readable codes and a `degradedMode` indicator when a service is in fallback.
- Per-call rate limiting and audit; PII-minimized payloads.

---

## 5. Data model (canonical entities)

Implement as SQLAlchemy models + Pydantic schemas. Use UUID PKs, `created_at`/`updated_at`, soft-delete where clinical.

| Entity | Purpose | Key fields |
|---|---|---|
| `Patient` | Demographics & safety context | `sex, age, allergies[], medications[], problem_list[]` (from EHR via adapter) |
| `Encounter` | One consultation | `patient_id, symptom_text, vitals{}, lang, attending, status, timestamp` |
| `SymptomSet` | Coded symptoms | `coded[], onset, severity, duration, laterality, negatives[]` |
| `DiagnosisEpisode` | KB learning unit | `symptom_text, diagnosis, icd, treatment{}, outcome(0..1), embedding(vector), source, snapshot_id` |
| `Medication` | For interaction screening | `drug, class, dose, route` (current & historical) |
| `Suggestion` | What the engine returned | `encounter_id, kind, payload{}, model_version, ruleset_version, drugref_version` |
| `Decision` | What the doctor confirmed | `confirmed_diagnosis, overridden, override_reason, physician` |
| `AcuityScore` | Triage band | `band, factors{weights}, trend, timestamp` |
| `AuditEvent` | Tamper-evident trail | `actor, action, target, detail{}, prev_hash, hash, ts` |
| `OutcomeRecord` | Recovery signal | `scale, readmission_flag, follow_up_status` |

`outcome` (0–1 recovery signal) is what lets the engine weight plans that **actually worked**. `Decision` is both audit record and training signal. Store `embedding` in a pgvector column (HNSW/IVFFlat index); maintain a code-system map (SNOMED CT / ICD-10 + Chinese clinical modification) in config.

---

## 6. AI engine — modular, hybrid, Zhipu-powered

Layout `app/engine/` so each layer is independently swappable and testable:

| Module | Role | Production implementation |
|---|---|---|
| `embeddings.py` | text → vector | **Zhipu embedding** API (`embedding-3`), config-driven; cache; local hashing fallback when offline |
| `vector_index.py` | nearest-neighbour search | **pgvector** (HNSW); in-process cosine fallback for SQLite |
| `classify.py` | retrieval-weighted vote → calibrated probs | outcome-weighted k-NN + isotonic/temperature calibration; pluggable for a GBM/neural ensemble later |
| `ood.py` | out-of-distribution detector | distance-to-manifold / low-similarity trip → low-confidence/escalation path |
| `rules.py` | red flags + do-not-miss, evaluated **last** | declarative, versioned rule set; deterministic; hard veto |
| `drug_safety.py` | allergy / interaction / dosing screen | severity model + cross-reactivity + renal/geriatric/pediatric dosing bounds; versioned drug reference |
| `recommend.py` | treatment from best-outcome episodes | outcome-weighted retrieval → candidate plan/meds → safety screen |
| `reasoner.py` | **Zhipu GLM** deep-analysis / RAG layer | grounded, **citation-required**, rules-vetoed; behind `LLM_REASONING` flag |
| `labels.py` | bilingual condition/drug names | EN/ZH terminology service |
| `orchestrator.py` | runs the pipeline, intent detection | assembles differential + treatment, stamps versions |

### 6.1 Pipeline (the safety contract — do not reorder)
```
patient   = enrich(symptoms, ehr_context)        # age, meds, labs, allergies, negatives
neighbors = retrieve(patient, knowledge_base)     # pgvector ANN over episode embeddings
probs     = classify(patient, neighbors)          # outcome-weighted, calibrated
probs     = apply_rules(probs, patient)           # red flags + do-not-miss surfacing (LAST)
ood_flag  = detect_ood(patient, neighbors)
dx        = rank_and_explain(probs, neighbors)    # ordered differential + evidence
# optional, flagged:
dx        = llm_reason(dx, neighbors)             # Zhipu GLM, grounded + cited, rules re-vetoed

rx = recommend_treatment(dx, knowledge_base)      # weighted by recovery outcome
rx = safety_screen(rx, patient.meds, patient.allergies)  # interactions, dose, allergy — hard veto
return dx, rx   # requiresPhysicianConfirmation: true — never auto-committed
```

### 6.2 Zhipu GLM integration (MUST)
- **Provider abstraction:** `app/ai/provider.py` defines `LLMProvider` (chat/`reason`) and `EmbeddingProvider` (`embed`) interfaces. Implement `ZhipuProvider` against Zhipu's **OpenAI-compatible** API.
  - Base URL (China): `https://open.bigmodel.cn/api/paas/v4` (configurable; international endpoint swappable). Auth via `ZHIPU_API_KEY`.
  - Defaults (override via env): chat model `glm-4.6`, embedding model `embedding-3`. Keep model names in config — **verify the exact current model identifiers against Zhipu's docs at build time** and update defaults if they changed.
  - Use the `openai` Python SDK pointed at the Zhipu base URL **or** a thin httpx client — either is fine; keep it isolated behind the interface.
- **Optimized for Chinese clinical text:** prompts, terminology, and embeddings must work in Chinese; `lang` controls output language. The reasoner's system prompt enforces: ground every claim in a retrieved episode, cite it, never invent drugs/doses, defer to the rules layer, and output the structured JSON contract.
- **Resilience:** timeouts, retries with backoff, and a **graceful fallback** to retrieval+rules ("degraded mode — reasoner offline") if Zhipu is unreachable. Never block the response indefinitely on the LLM.
- **Safety:** every LLM-generated claim must cite a retrieved source or be suppressed; the rules/safety layer still runs last and can veto LLM output. Token/cost budget is bounded and logged.

### 6.3 Seed data
- `data/episodes.json` — seed outcome-labelled episodes (provide a realistic but clearly-illustrative sample set; structure for scaling to the 3,000+ Chinese seed corpus, embedded on load/migration). Mark as illustrative; real data is de-identified/licensed and loaded out-of-band.
- `data/drug_reference.json` — interactions, allergy classes, cross-reactivity, dosing bounds (versioned). Replace with a licensed China formulary in production.

---

## 7. Degraded-mode behavior (implement and test)

| Failure | Behavior | What still works |
|---|---|---|
| Classifier offline | "Degraded mode" banner via `degradedMode` | retrieval + rules still produce a differential |
| Zhipu reasoner offline | "reasoner offline" note | full non-LLM pipeline still answers |
| External drug reference offline | "reduced coverage" flag | local interaction set screens; contraindication blocks hold |
| Triage scorer offline | manual ordering with banner | queue still visible; vitals shown |
| HIS write-back failing | sign-off queued, retried, surfaced; reconciliation job | clinician informed; nothing silently dropped |
| Vector index slow | cascade to cached/precomputed results | UI stays responsive |

---

## 8. Security, auth & RBAC (MUST)

- **OIDC/OAuth2** bearer-token validation middleware; dev mode issues/accepts a local signed dev token so the stack runs without the hospital IdP, with the real JWKS-validation path implemented behind config.
- **RBAC** enforced at the API boundary per this matrix (least-privilege): Physician, Nurse, Pharmacist, Admin, Safety/ML, IT/Operator. Key rules: only **Physician** can confirm a diagnosis and sign a prescription; only **Pharmacist** verifies/holds; contraindication override requires a typed reason and is logged + surfaced to the pharmacist; audit export limited to Admin/Safety/IT.
- **Separation of duties:** the role that authors a model release cannot approve it (Safety/ML approves); clinical sign-off is physician-only.
- **Data protection:** TLS in transit; AES-256-at-rest expectation documented; PostgreSQL **row-level security** policies; encrypted Redis with short TTL; secrets only from env/secret manager; **append-only/WORM-style audit table** with integrity hashing; configurable data residency via `DATABASE_URL`/region config; de-identification for learning data.
- **Compliance posture:** CDS (non-autonomous), aligned to **PIPL** + China data-security regime for the pilot, GDPR-equivalent controls as portable baseline. Build the evidence hooks (versioning, audit, validation datasets, post-market surveillance counters) in from day one.

---

## 9. Project layout

```
backend/
  app/
    main.py                 # FastAPI app, middleware, router mounting, CORS, lifespan
    config.py               # pydantic-settings; all env config + feature flags
    deps.py                 # DI: db session, current_user, rbac
    db/                     # engine, session, base, alembic env
    models.py               # SQLAlchemy canonical entities
    schemas.py              # Pydantic request/response contracts (v1 chat + v2)
    routers/
      clinical.py           # POST /api/clinical, GET /api/health
      encounters.py         # /v2/encounters/* (symptoms, differential, diagnosis, prescription)
      prescriptions.py      # /v2/prescriptions/{id}/sign|verify
      episodes.py           # POST /v2/episodes
      triage.py             # GET /v2/triage/queue
      outcomes.py           # POST /v2/encounters/{id}/outcome
      audit.py              # GET /v2/audit/events
    engine/                 # embeddings, vector_index, classify, ood, rules,
                            #   drug_safety, recommend, reasoner, labels, orchestrator
    ai/                     # provider.py (interfaces) + zhipu.py
    integration/            # fhir adapter, canonical mapping, write-back queue, reconciliation
    learning/              # data-quality pipeline, active-learning queue, snapshots, model registry, eval gates
    security/               # oidc, rbac, audit hash-chain
    observability/          # logging, metrics, tracing
  data/                     # episodes.json, drug_reference.json, code maps
  alembic/                  # migrations
  tests/                    # unit, rules golden suite, contract, integration, e2e
  Dockerfile
  docker-compose.yml
  requirements.txt / pyproject.toml
  .env.example
  README.md
```

---

## 10. Docker & run (MUST work out of the box)

- **Multi-stage `Dockerfile`** (slim, non-root, healthcheck).
- **`docker-compose.yml`** services: `api` (8787), `postgres` (pgvector image, e.g. `pgvector/pgvector:pg16`), `redis`. Volumes for DB; healthchecks; `api` waits for healthy DB; runs Alembic migrations + seed-load on start.
- **Local dev without Docker:** `uvicorn app.main:app --port 8787` works on SQLite with zero setup.
- `.env.example` documents: `DATABASE_URL`, `REDIS_URL`, `ZHIPU_API_KEY`, `ZHIPU_BASE_URL`, `LLM_CHAT_MODEL`, `EMBEDDING_MODEL`, `LLM_REASONING`, `CORS_ORIGINS`, `OIDC_ISSUER`/`OIDC_AUDIENCE`/`OIDC_JWKS_URL`, `DEV_AUTH`, model/rule/drugref version strings, residency/region.
- Acceptance smoke test:
```bash
docker compose up -d
curl localhost:8787/api/health
curl -X POST localhost:8787/api/clinical -H 'content-type: application/json' \
  -d '{"messages":[{"role":"doctor","text":"67M chest pain radiating to left arm, diaphoretic, HR 118 BP 92/60"}],"lang":"en"}'
```
The second call MUST return a red-flag-first differential (ACS surfaced) with version stamps and `requiresPhysicianConfirmation: true`.

---

## 11. Testing & acceptance (MUST)

- **Unit** tests for scoring, calibration, mappers, hash-chain.
- **Rules/safety golden suite** — every red-flag, allergy, interaction, dosing, do-not-miss case; **100% pass is a hard gate**. Include: penicillin-allergy → amoxicillin **blocked** with azithromycin offered; warfarin interaction flagged at correct severity; pediatric/geriatric/renal dosing bounds; ACS/sepsis/stroke red-flag surfacing even at low probability.
- **Contract tests** validating both the v1 chat JSON shape and the v2 schemas exactly as in §4 (so the existing frontend works).
- **Integration** tests: episode capture → embed → live-index → retrievable on next differential; diagnosis confirm logs a `Decision` + audit event; audit hash-chain verifies and is tamper-evident.
- **Degraded-mode** tests for each row in §7 (especially: Zhipu offline → pipeline still answers; contraindication block still holds).
- **AuthZ** tests: nurse cannot confirm diagnosis; pharmacist cannot sign Rx; audit export blocked for non-privileged roles.
- **Latency** check: differential p95 < 5 s on seed data (document method).
- Provide a `make test` / documented command; CI-friendly. `ruff` + `mypy` clean.

**Final verification step:** run the full test suite, the Docker smoke test, and a tamper-test on the audit chain; produce a short `BUILD_REPORT.md` summarizing what's real vs. seam-stubbed, test results, and how to point it at the real Zhipu key + hospital FHIR endpoint.

---

## 12. Deliverables & working method

1. Start by scaffolding the repo, `config.py`, DB layer, and a green `GET /api/health` — confirm it runs — **then** build outward pillar by pillar.
2. Implement `POST /api/clinical` end-to-end early (it's what the frontend uses) and keep it passing as you add `/v2`.
3. Commit per phase with clear messages. Keep the build runnable at every commit.
4. Do not invent clinical facts: the drug reference and episodes are explicitly illustrative seed data; structure for replacement with licensed/real de-identified Chinese clinical data.
5. Write a clear `README.md` (run, env, architecture, what's real vs. seam) and `BUILD_REPORT.md` at the end.
6. Flag anything ambiguous before making an irreversible architectural choice. Honor every **MUST** and the §1 invariants without exception.

> **The through-line:** keep the physician in command, always show the reasoning, run safety last with hard veto, and stamp + audit everything. Those are the safety mechanism, not just principles.
