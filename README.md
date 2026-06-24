<div align="center">

# 🩺 MediSense

### AI Clinical Decision Support Platform

*The AI assistant that diagnoses alongside the doctor.*

[![Status](https://img.shields.io/badge/status-pilot-blue.svg)]()
[![Version](https://img.shields.io/badge/version-1.0-0F766E.svg)]()
[![Stage](https://img.shields.io/badge/stage-documentation-4F46E5.svg)]()
[![Deployment](https://img.shields.io/badge/first%20deployment-China%20hospital-DC2626.svg)]()
[![License](https://img.shields.io/badge/license-proprietary-lightgrey.svg)]()

</div>

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

A **hybrid architecture** combines case-based retrieval, a learned classifier, and an explicit clinical rules layer. No single technique is trusted alone — the rules layer can hard-override statistics so that safety (allergies, contraindications) always wins.

---

## 🚀 Key Features

- **Differential diagnosis** with calibrated probabilities, not a single black-box answer.
- **Anti-anchoring by design** — surfaces a broad differential including "do-not-miss" conditions even at low probability.
- **Explainable evidence drawer** — every suggestion shows supporting & contradicting signals, similar past cases, and the next-best test.
- **Real-time drug safety** — 100% of prescription suggestions screened for drug–drug interactions, allergies, dosing, and duplicate therapy, with a four-level severity model.
- **Acuity-based triage** — live, auto-ranked patient queue (Critical / Urgent / Routine) with active escalation alerts.
- **Standards-based integration** — HL7 FHIR resources (`Patient`, `Condition`, `MedicationRequest`, `Observation`, `AllergyIntolerance`) with an adapter layer for legacy HIS.
- **Continuous learning** — outcome-labelled episodes improve the model over time; every physician override is a training signal.
- **Human-in-the-loop & full audit trail** — no diagnosis recorded or prescription issued without explicit physician sign-off.
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

| Document | Description |
|---|---|
| [`MediSense_Product_Technical_Documentation.md`](./MediSense_Product_Technical_Documentation.md) | Full product & technical specification — vision, personas, features, UX, AI architecture, data model, API surface, security & compliance. |
| [`MediSense_Product_Technical_Documentation.pdf`](./MediSense_Product_Technical_Documentation.pdf) | The same specification as a designed, presentation-ready PDF. |
| [`MediSense_Product_Development_Roadmap.md`](./MediSense_Product_Development_Roadmap.md) | How the platform improves and becomes more efficient — 8 improvement themes, prioritization, phased plan, KPIs. |

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
├── README.md                                          # You are here
├── MediSense_Product_Technical_Documentation.md       # Product & technical spec
├── MediSense_Product_Technical_Documentation.pdf      # Designed PDF version
└── MediSense_Product_Development_Roadmap.md           # Improvement & optimization plan
```

> 📌 This repository currently holds the **product & technical documentation**. Implementation is planned per the roadmap.

---

## 🤝 Contributing

This is an internal, proprietary project. For access, questions, or collaboration, please contact the MediSense team.

---

<div align="center">

**MediSense** · AI Clinical Decision Support
*Confidential · v1.0 · June 2026*

</div>
