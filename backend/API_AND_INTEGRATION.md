# MediSense — Backend API & Frontend Integration Guide

Detailed reference for the MediSense backend: data model, every route with
example payloads, the engine internals, and exactly what the frontend needs to
consume it. For the high-level summary see `BACKEND_OVERVIEW.md`; for run/setup
see `README.md`.

---

## 1. Architecture at a glance

```
┌────────────────────────────────────────────────────────────┐
│ React chat UI (frontend/)                                   │
│   src/lib/api.ts  ──POST /api/clinical──►                    │
└───────────────────────────┬────────────────────────────────┘
                            │ JSON over HTTP (CORS)
┌───────────────────────────▼────────────────────────────────┐
│ FastAPI app (app/main.py)                                    │
│   routers/  clinical · encounters · episodes · triage ·      │
│             audit · health                                    │
│   engine/   embeddings → vector_index → classify →           │
│             rules/safety (last) → recommend + drug_safety     │
│   models.py / schemas.py   canonical data + typed contracts   │
└───────────────────────────┬────────────────────────────────┘
                            │ async SQLAlchemy
┌───────────────────────────▼────────────────────────────────┐
│ PostgreSQL + pgvector (prod)  ·  SQLite (default)  ·  Redis  │
└─────────────────────────────────────────────────────────────┘
```

Pipeline order is the safety contract: **retrieve → classify → calibrate →
rules LAST**. The rules/safety layer can override any statistical output. No
suggestion is emitted without version stamps and `requiresPhysicianConfirmation`.

---

## 2. Data model (canonical entities)

| Entity | Purpose | Key fields |
|---|---|---|
| `Patient` | Demographics & safety context | `sex, age, allergies[], medications[], problem_list[]` |
| `Encounter` | One consultation | `patient_id, symptom_text, vitals{}, lang` |
| `DiagnosisEpisode` | KB learning unit | `symptom_text, diagnosis, icd, treatment{}, outcome(0..1), embedding[]` |
| `Suggestion` | What the engine returned | `encounter_id, kind, payload{}, model_version, ruleset_version, drugref_version` |
| `Decision` | What the doctor confirmed | `confirmed_diagnosis, overridden, override_reason, physician` |
| `AuditEvent` | Tamper-evident trail | `actor, action, target, detail{}, prev_hash, hash` |

`outcome` (recovery signal, 0–1) is what lets the engine weight plans that
*actually worked*, not just plausible ones. `Decision` is both the audit record
and a training signal (every override is a lesson).

### Shared enums
- **Confidence band:** `High | Moderate | Low | Watch` (`Watch` = pinned do-not-miss).
- **Interaction severity:** `Contraindicated | Major | Moderate | Minor`
  (`Contraindicated` = hard block).

---

## 3. Routes

Base URL in dev: `http://localhost:8787`. Interactive docs: `/docs`.

### 3.1 Chat surface (what the UI uses today)

#### `POST /api/clinical`
Runs the engine over a conversation and returns the structured reply the chat UI
renders.

**Request**
```json
{
  "messages": [
    { "role": "doctor", "text": "62F, 3 days fever, productive cough, right-sided pleuritic chest pain. RR 22, SpO2 94%." }
  ],
  "lang": "en"
}
```
`role` is `doctor` or `ai`; only doctor turns form the clinical case. A legacy
`{ "prompt": "...", "lang": "en" }` body is also accepted. Add a prescriptive
turn (e.g. *"what should I prescribe?"*) to also get a `treatment` block.

**Response** — `{ "text": "<JSON string>" }`; parse `text` into:
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
`probability` here is **0–100**. When the doctor asks to treat, `treatment` is:
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

#### `GET /api/health`
```json
{ "ok": true, "episodes": 24, "modelVersion": "dx-2026.06.1-pilot",
  "ruleSetVersion": "rules-2026.06.1", "drugRefVersion": "drugref-2026.06.1",
  "llmReasoning": false, "datastore": "sqlite" }
```

### 3.2 Versioned clinical API (`/v2`) — structured flow

Use this when you want the spec-shaped flow (separate confirm + prescribe steps)
rather than the single chat call. **Here `probability` is 0–1.**

| Method & path | Body → Response |
|---|---|
| `PUT /v2/encounters/{id}/symptoms` | `SymptomSubmission` → `{encounterId, ok}` |
| `GET /v2/encounters/{id}/differential` | – → `DifferentialResponse` |
| `POST /v2/encounters/{id}/diagnosis` | `DiagnosisConfirmation` → `{encounterId, confirmed, logged}` |
| `POST /v2/encounters/{id}/prescription` | `PrescriptionRequest` → `PrescriptionResponse` |
| `POST /v2/episodes` | `EpisodeIn` → `{episodeId, indexed}` |
| `GET /v2/triage/queue?limit=20` | – → `{queue:[…]}` |
| `GET /v2/audit/events?limit=50` | – → `{events:[…]}` |

**SymptomSubmission**
```json
{ "symptomText": "24yo asthmatic, wheeze, breathless, cough", "age": 24, "sex": "M",
  "vitals": {"spo2": 93, "hr": 96}, "allergies": [], "medications": [], "lang": "en" }
```
**DifferentialResponse** (each item)
```json
{ "condition": "Acute asthma exacerbation", "icd": "J45.901", "probability": 0.62,
  "confidence": "High", "supporting": [], "contradicting": [], "similarCases": 2,
  "typicalOutcomes": {"improved": 0.89, "readmission_30d": 0.0}, "nextBestTest": "Peak expiratory flow" }
```
Top-level also returns `redFlags[]`, `ood` (out-of-distribution), `modelVersion`,
`ruleSetVersion`, `requiresPhysicianConfirmation`.

**DiagnosisConfirmation** → logs a `Decision` + audit event
```json
{ "condition": "Acute asthma exacerbation", "icd": "J45.901",
  "overridden": false, "overrideReason": null, "physician": "Dr Lin" }
```
**PrescriptionRequest** → `PrescriptionResponse {encounterId, drugRefVersion, ruleSetVersion, treatment}`
```json
{ "condition": "Acute asthma exacerbation", "allergies": ["penicillin"], "currentMedications": ["warfarin"], "lang": "en" }
```
**EpisodeIn** — feeds the continuous-learning loop; embeds + live-indexes
```json
{ "symptomText": "...", "diagnosis": "Influenza", "icd": "J11.1",
  "treatment": {"plan": [], "medications": []}, "outcome": 0.93, "nextBestTest": "PCR" }
```

### 3.3 curl quickstart
```bash
curl localhost:8787/api/health
curl -X POST localhost:8787/api/clinical -H 'content-type: application/json' \
  -d '{"messages":[{"role":"doctor","text":"67M chest pain radiating to left arm, diaphoretic, HR 118 BP 92/60"}],"lang":"en"}'
```

---

## 4. Engine internals (where to extend)

| Module | Role | Swap for production |
|---|---|---|
| `engine/embeddings.py` | text → vector | clinical sentence encoder |
| `engine/vector_index.py` | nearest-neighbour search | pgvector / Milvus |
| `engine/classify.py` | outcome-weighted vote → calibrated probs | GBM/neural ensemble + isotonic calibration |
| `engine/rules.py` | red flags + do-not-miss, evaluated last | full declarative rule set |
| `engine/drug_safety.py` | allergy/interaction/dosing screen | licensed interaction DB |
| `engine/recommend.py` | treatment from best-outcome episodes | outcome model |
| `engine/labels.py` | bilingual condition names | SNOMED/ICD terminology service |
| `engine/orchestrator.py` | runs the pipeline, intent detection | — |

Reference data: `data/episodes.json` (seed KB) and `data/drug_reference.json`
(interactions, allergy classes, dosing) — both illustrative; replace with real,
de-identified / licensed data.

---

## 5. Frontend integration

### 5.1 Already wired
- `src/lib/api.ts` posts `{ messages, prompt, lang }` to `/api/clinical`,
  parses the JSON, normalizes confidence bands, and falls back to an offline
  stub if the backend is unreachable.
- `src/types.ts` includes `Diagnosis` + `Treatment` / `Medication` / `SafetyFlag`.
- `DifferentialCard.tsx` renders red flag, summary, ranked rows, next-best test;
  `TreatmentCard.tsx` renders the plan, medications, and color-graded safety flags.
- Vite proxies `/api → http://localhost:8787` (`vite.config.ts`); bilingual
  EN/ZH strings in `lib/i18n.ts`.

### 5.2 Config the frontend needs
- `VITE_API_URL` (defaults to `/api/clinical`) — set only if the API isn't proxied.
- `VITE_PROXY_TARGET` (dev) — backend origin for the Vite proxy.
- Backend `CORS_ORIGINS` must include the frontend origin.

### 5.3 Recommended frontend work (not built yet)
1. **Auth** — `LoginModal.tsx` is UI-only. Wire to an OIDC flow; send the bearer
   token on every request; gate the app on session.
2. **Structured patient context** — capture allergies / current meds / vitals as
   fields (not just free text) and send them so the safety screen is exact. Today
   the engine best-effort parses them from the chat text.
3. **Triage board view** — consume `GET /v2/triage/queue` for a Critical/Urgent/
   Routine queue (a core pillar; no screen yet).
4. **Evidence drawer** — show `similarCases`, `typicalOutcomes`, supporting/
   contradicting signals from the `/v2/differential` response.
5. **Confirm + prescribe actions** — buttons that call `/v2/.../diagnosis` and
   `/v2/.../prescription` so decisions are logged to the audit trail.
6. **Degraded-mode + error UI** — surface `ood`, missing-key, and non-200 states
   instead of silently using the offline stub.
7. **Display version stamps** — show `modelVersion` / `ruleSetVersion` for
   traceability.

### 5.4 Minimal call example
```ts
const res = await fetch("/api/clinical", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ messages: [{ role: "doctor", text }], lang }),
});
const dx = JSON.parse((await res.json()).text); // -> Diagnosis (+ treatment)
```

---

## 6. Security & compliance hooks (pilot status)
Implemented: hash-chained audit trail, version stamping, human-in-the-loop flag,
hard safety vetoes, configurable data residency via `DATABASE_URL`.
To add before production: OIDC/RBAC auth, row-level security on Postgres,
encryption at rest, FHIR write-back at the hospital boundary, Alembic migrations.
