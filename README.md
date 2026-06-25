<div align="center">

# 🩺 MediSense

### AI Clinical Decision Support Platform

*The AI assistant that diagnoses alongside the doctor.*

[![Status](https://img.shields.io/badge/status-pilot-blue.svg)]()
[![Version](https://img.shields.io/badge/version-2.0-0F766E.svg)]()
[![Backend](https://img.shields.io/badge/backend-FastAPI%20·%20Postgres%2Fpgvector-009688.svg)]()
[![Frontend](https://img.shields.io/badge/frontend-React%20·%20Vite-4F46E5.svg)]()
[![Tests](https://img.shields.io/badge/tests-40%20passing-059669.svg)]()
[![Deployment](https://img.shields.io/badge/first%20deployment-China%20hospital-DC2626.svg)]()
[![License](https://img.shields.io/badge/license-proprietary-lightgrey.svg)]()

</div>

> **This repo is a runnable pilot.** A FastAPI backend (hybrid AI engine + safety
> layer + audit) and a React clinician UI, wired together. One command —
> [`./run.sh`](#-quick-start) — brings up both.

---

## Overview

**MediSense** is an AI-powered clinical decision-support platform that sits beside the physician at the point of care. It learns from a knowledge base of real diagnostic episodes — **patient symptoms → doctor's diagnosis → treatment & prescription → recovery outcome** — and uses that knowledge to assist with the next patient.

When a new patient presents, MediSense:

- 🔍 reads their symptoms and history,
- 📊 compares them against thousands of similar past cases,
- 🧠 returns a **ranked differential diagnosis** with calibrated probabilities and a transparent explanation,
- 💊 proposes treatment and prescriptions — each **automatically screened** for drug interactions, allergies, and dosing,
- 🚨 and continuously **prioritizes patients** by how critical and urgent their condition is.

> **Core principle: assist, never replace.** Every output is a *suggestion with its reasoning attached*. The licensed physician always makes the final decision — MediSense exists to make that decision faster, safer, and better-informed.

The initial version is trained and refined on **Chinese clinical data** for a first deployment in a hospital in China.

---

## ✨ The Four Pillars

| Pillar | What it does |
|---|---|
| 🩻 **Diagnose** | Ranks probable conditions from symptoms & history with confidence and evidence. |
| 💊 **Prescribe** | Recommends treatment & medication, auto-screened for interactions and allergies. |
| 🚦 **Triage** | Scores acuity & urgency to order the patient queue and escalate deterioration. |
| 🔗 **Integrate** | Reads from and writes back to hospital systems (HIS / EHR) via FHIR / HL7. |

These form a **closed learning loop**: diagnosis informs prescription → prescription depends on the integrated record → the record feeds triage → the doctor's confirmed outcome flows back into the knowledge base, sharpening the next diagnosis.

---

## 🧠 How It Works

```
  Symptoms ──▶ Enrich with EHR context (age, meds, allergies, labs)
                        │
                        ▼
        ┌───────────────────────────────────┐
        │  HYBRID AI ENGINE                  │
        │  1. Retrieval  (similar past cases)│
        │  2. Classifier (calibrated probs)  │
        │  3. Rules/Safety (hard guardrails) │
        └───────────────────────────────────┘
                        │
        ┌───────────────┴────────────────┐
        ▼                                ▼
  Ranked Differential            Screened Prescription
  (probability + evidence)       (interaction/allergy safe)
                        │
                        ▼
            👨‍⚕️ Physician confirms / edits / overrides
                        │
                        ▼
        Written back to EHR + outcome feeds the knowledge base
```

A **hybrid architecture** combines case-based retrieval (pgvector ANN over
outcome-labelled episodes), an outcome-weighted calibrated classifier, and an
explicit clinical rules layer **evaluated last**. No single technique is trusted
alone — the rules layer can hard-override statistics so that safety (allergies,
contraindications) always wins. Deep reasoning is powered by **Zhipu GLM** (a
Chinese LLM) and Zhipu embeddings, behind a swappable provider interface.

---

## 🚀 Quick Start

```bash
git clone https://github.com/nimadorostkar/MediSense.git
cd MediSense
./run.sh                 # local dev: backend (SQLite) + frontend, hot reload
#   or
./run.sh docker          # backend via Docker (Postgres + pgvector + Redis) + frontend
```

Then open **http://localhost:5173** (UI) — the backend API is on
**http://localhost:8787** (interactive docs at `/docs`). `Ctrl-C` stops both.

**Try it:** sign in (e.g. `li.wei@hospital.cn` / any 6+ char password), then enter
a case like *"67M chest pain radiating to left arm, diaphoretic, HR 118 BP 92/60"* —
you'll get a red-flag-first differential, version stamps, and (on a "what should I
prescribe?" turn) a safety-screened treatment card. Sign in as `nurse.zhang@…` or
`pharmacist.chen@…` to act in those RBAC roles.

> Run the parts separately if you prefer — see [`backend/docs/GUIDE.md`](./backend/docs/GUIDE.md).

---

## 🧰 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12 · FastAPI · async SQLAlchemy 2.0 · Pydantic v2 |
| **Datastore** | PostgreSQL 16 + **pgvector** (HNSW ANN) · SQLite zero-setup fallback · Alembic migrations |
| **AI engine** | Zhipu GLM reasoning + `embedding-3` (swappable provider) · outcome-weighted k-NN + calibration · declarative rules/safety |
| **Cache / events** | Redis (optional per-encounter cache + pub/sub) |
| **Auth** | OAuth2 / OIDC bearer + RBAC · local dev-token path |
| **Frontend** | React · Vite · TypeScript · Tailwind CSS |
| **Ops** | Docker + docker-compose · Prometheus `/metrics` · structured JSON logging · pytest (40 tests) · ruff + mypy |

---

## 🔌 API Surface

The React UI talks to the backend over these routes (full contract in
[`docs/API_AND_INTEGRATION.md`](./docs/API_AND_INTEGRATION.md)):

| Surface | Endpoints |
|---|---|
| **Chat** | `POST /api/clinical` · `GET /api/health` |
| **Auth** | `POST /api/auth/login` · `GET /api/auth/me` · `GET /api/auth/config` |
| **Clinical (v2)** | `PUT /v2/encounters/{id}/symptoms` · `GET …/differential` · `POST …/diagnosis` · `POST …/prescription` |
| **Prescriptions** | `POST /v2/prescriptions/{id}/sign` · `…/verify` |
| **Learning / triage / audit** | `POST /v2/episodes` · `GET /v2/triage/queue` · `POST /v2/encounters/{id}/outcome` · `GET /v2/audit/events` |
| **Ops** | `GET /metrics` · `GET /docs` |

Every response is version-stamped (`modelVersion` / `ruleSetVersion` /
`drugRefVersion`) and carries `requiresPhysicianConfirmation`. Write endpoints
accept idempotency keys; all actions are written to an immutable, hash-chained
audit trail.

---

## 🚀 Key Features

- **Differential diagnosis** with calibrated probabilities, not a single black-box answer.
- **Anti-anchoring by design** — surfaces a broad differential including "do-not-miss" conditions even at low probability.
- **Explainable evidence drawer** — every suggestion shows supporting & contradicting signals, similar past cases, and the next-best test.
- **Real-time drug safety** — 100% of prescription suggestions screened for drug–drug interactions, allergies, dosing, and duplicate therapy, with a four-level severity model.
- **Acuity-based triage** — live, auto-ranked patient queue (Critical / Urgent / Routine) with active escalation alerts.
- **Standards-based integration** — HL7 FHIR resources (`Patient`, `Condition`, `MedicationRequest`, `Observation`, `AllergyIntolerance`) with an adapter layer for legacy HIS.
- **Continuous learning** — outcome-labelled episodes improve the model over time; every physician override is a training signal.
- **Human-in-the-loop & tamper-evident audit** — nothing is committed without physician sign-off; every view/suggestion/override/sign-off is written to an immutable, hash-chained audit trail.
- **OIDC + RBAC** — role-scoped access (Physician / Nurse / Pharmacist / Admin / Safety / IT) enforced at the API boundary; only a physician confirms a diagnosis or signs an Rx.
- **Graceful degradation** — a downed classifier / reasoner / drug reference / triage scorer yields a labelled, reduced answer; hard safety blocks still hold.
- **Bilingual (Chinese / English)** interface, localizable terminology and formularies.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER — clinician web/desktop app           │
│  Triage board · Patient view · Diagnosis · Prescription   │
├──────────────────────────────────────────────────────────┤
│  APPLICATION & API LAYER                                  │
│  Auth · session · routing · write-back · audit            │
├──────────────────────────────────────────────────────────┤
│  AI SERVICES                                              │
│  Retrieval · Classification · Rules/Safety · Triage score │
├──────────────────────────────────────────────────────────┤
│  DATA & KNOWLEDGE LAYER                                   │
│  Episode KB · vector index · drug reference · patient model│
├──────────────────────────────────────────────────────────┤
│  INTEGRATION ADAPTER — FHIR / HL7 → hospital HIS / EHR     │
└──────────────────────────────────────────────────────────┘
```

---

## 📚 Documentation

**Run & build the system**

| Document | Description |
|---|---|
| [`backend/docs/README.md`](./backend/docs/README.md) | Backend overview — run, env, architecture, what's real vs. seam. |
| [`backend/docs/GUIDE.md`](./backend/docs/GUIDE.md) | Short guide: how it works · how to add KB data · how to run. |
| [`backend/docs/PRODUCTION_SETUP.md`](./backend/docs/PRODUCTION_SETUP.md) | **Add AI · add symptom/diagnosis data · run as production** — end-to-end. |
| [`backend/docs/AI_SETUP.md`](./backend/docs/AI_SETUP.md) | Turning on the Zhipu GLM AI layer (embeddings + reasoning). |
| [`backend/docs/BUILD_REPORT.md`](./backend/docs/BUILD_REPORT.md) | Verification results · what's real vs. seam-stubbed. |
| [`docs/API_AND_INTEGRATION.md`](./docs/API_AND_INTEGRATION.md) | Full API contract + frontend integration reference. |

**Product & specification**

| Document | Description |
|---|---|
| [`docs/MediSense_Production_Specification.md`](./docs/MediSense_Production_Specification.md) | The production blueprint the backend is built against (engineering-grade). |
| [`docs/MediSense_Product_Technical_Documentation.md`](./docs/MediSense_Product_Technical_Documentation.md) | Full product & technical specification — vision, personas, UX, AI architecture, data model, security. |
| [`docs/MediSense_Product_Development_Roadmap.md`](./docs/MediSense_Product_Development_Roadmap.md) | Improvement & optimization plan — themes, prioritization, phased plan, KPIs. |

---

## 🗺️ Roadmap

| Phase | Focus |
|---|---|
| **1 · Foundation & Pilot** | Train on 3,000+ Chinese episodes; integrate one HIS; deploy diagnosis engine + drug-safety screen. |
| **2 · Full Workflow** | Triage board, outcome-feedback capture, continuous-learning loop; expand departments. |
| **3 · Multi-site & Depth** | Onboard more hospitals via the adapter; deepen specialty coverage; admin analytics. |
| **4 · Scale & New Markets** | Localization of language, formularies & regulatory evidence per market. |

See the [Development & Optimization Roadmap](./MediSense_Product_Development_Roadmap.md) for the detailed improvement plan (multimodal inputs, ambient voice scribe, federated learning, and more).

---

## 🔐 Safety, Privacy & Compliance

- **Human-in-the-loop, always** — the system cannot act autonomously on a patient.
- **Fail-safe defaults** — on low confidence or missing data, MediSense asks rather than guesses.
- **Hard safety rules win** — allergy and contraindication blocks override any statistical suggestion.
- **Data protection** — encryption in transit & at rest, role-based access, data minimization, de-identification for learning, configurable data residency.
- **Accountability** — full audit trail; every output traceable to a model version.
- **Regulatory posture** — positioned as clinical decision support; built to produce validation and data-governance evidence for each market's regulator (beginning with China's NMPA).

> ⚠️ **Disclaimer:** MediSense is a decision-support tool intended to **assist, not replace**, licensed clinicians. All clinical examples in the documentation are illustrative. It operates under the applicable medical-device and data-protection requirements of each market in which it is deployed.

---

## 📂 Project Structure

```
MediSense/
├── run.sh                  # one command to launch backend + frontend
├── backend/                # FastAPI clinical engine
│   ├── app/                #   config · models · schemas · engine/ · routers/ · ai/ · security/ …
│   ├── data/               #   illustrative seed KB · drug reference · code maps
│   ├── alembic/            #   migrations (schema + pgvector + HNSW index)
│   ├── tests/              #   rules golden suite · contract · integration · degraded · authz
│   ├── docker-compose.yml  #   api + postgres/pgvector + redis
│   └── docs/               #   README · GUIDE · AI_SETUP · BUILD_REPORT
├── frontend/               # React + Vite clinician chat UI
│   └── src/                #   components · hooks · lib/api.ts (talks to the backend)
└── docs/                   # product spec, technical docs, roadmap, API reference
```

> 📌 The backend and frontend are **implemented and connected**. The KB and drug
> reference ship as clearly-marked *illustrative* seed data, structured for
> replacement by the de-identified Chinese corpus and a licensed formulary
> (see [`backend/docs/BUILD_REPORT.md`](./backend/docs/BUILD_REPORT.md)).

---

## 🤝 Contributing

This is an internal, proprietary project. For access, questions, or collaboration, please contact the MediSense team.

---

<div align="center">

**MediSense** · AI Clinical Decision Support
*Confidential · v2.0 · June 2026*

</div>
