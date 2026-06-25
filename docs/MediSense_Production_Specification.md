# MediSense — Production Specification

**AI Clinical Decision Support Platform · The Complete Production Blueprint**

*Version 2.0 (Production) · June 2026 · Confidential — for product, engineering, clinical, security & regulatory leadership*
*Supersedes scope of: Product & Technical Documentation v1.0 and Development & Optimization Roadmap v1.0*
*First deployment: hospital pilot, China (NMPA jurisdiction)*

> **Purpose of this document.** The v1.0 documentation described *what MediSense is* and the roadmap described *how it improves*. This specification describes *how to build, ship, and operate the best possible production system* — a buildable, engineering-grade blueprint that an implementation team can execute against, a security team can audit, and a regulator can review. Every design decision is stated with its rationale, its failure modes, and its acceptance criteria.

---

## Table of Contents

**Part I — Product Definition**
1. [Executive Summary](#1-executive-summary)
2. [Product Vision, Scope & Non-Goals](#2-product-vision-scope--non-goals)
3. [Design Principles & Production Tenets](#3-design-principles--production-tenets)
4. [Users, Personas & Role Model](#4-users-personas--role-model)
5. [The Four Pillars & the Closed Learning Loop](#5-the-four-pillars--the-closed-learning-loop)

**Part II — Functional Specification**
6. [Diagnosis & Differential Probability Engine](#6-diagnosis--differential-probability-engine)
7. [Prescription & Drug-Interaction Safety](#7-prescription--drug-interaction-safety)
8. [Triage & Patient Prioritization](#8-triage--patient-prioritization)
9. [Hospital & EHR Integration](#9-hospital--ehr-integration)
10. [End-to-End User Flows](#10-end-to-end-user-flows)
11. [Screen-by-Screen UX Specification](#11-screen-by-screen-ux-specification)

**Part III — Technical Architecture**
12. [AI / ML Architecture](#12-ai--ml-architecture)
13. [Knowledge Base & Continuous Learning](#13-knowledge-base--continuous-learning)
14. [MLOps, Model Lifecycle & Evaluation](#14-mlops-model-lifecycle--evaluation)
15. [Data Model & Canonical Schema](#15-data-model--canonical-schema)
16. [System & Infrastructure Architecture](#16-system--infrastructure-architecture)
17. [API Surface & Integration Contracts](#17-api-surface--integration-contracts)

**Part IV — Production Readiness**
18. [Security, Privacy & Data Governance](#18-security-privacy--data-governance)
19. [Regulatory & Clinical Validation](#19-regulatory--clinical-validation)
20. [Design System](#20-design-system)
21. [Non-Functional Requirements](#21-non-functional-requirements)
22. [Deployment, Infrastructure & Operations](#22-deployment-infrastructure--operations)
23. [Observability, Reliability & Incident Response](#23-observability-reliability--incident-response)
24. [Quality Assurance & Test Strategy](#24-quality-assurance--test-strategy)
25. [Rollout Plan & Release Gates](#25-rollout-plan--release-gates)
26. [Success Metrics, KPIs & SLAs](#26-success-metrics-kpis--slas)
27. [Risk Register & Mitigations](#27-risk-register--mitigations)
28. [Open Questions & Decision Log](#28-open-questions--decision-log)
29. [Glossary](#29-glossary)

---
---

# Part I — Product Definition

## 1. Executive Summary

**MediSense** is an AI-powered clinical decision-support (CDS) platform that sits beside the physician at the point of care. It learns from a curated knowledge base of real, outcome-labelled diagnostic episodes — *patient symptoms → doctor's diagnosis → treatment & prescription → recovery outcome* — and applies that knowledge to assist with the next patient.

For each new patient, MediSense reads symptoms and history, compares them against thousands of similar past cases, and returns a **ranked differential diagnosis** with calibrated probabilities and a transparent explanation of *why*. It proposes evidence-aligned treatment and prescriptions, each **automatically screened** against the patient's drugs, allergies, age, and organ function before it is shown. Across a ward or clinic, it continuously **prioritizes patients** by acuity and urgency so the most fragile patient is never waiting at the back of the queue. Every confirmed outcome flows back into the knowledge base, sharpening the next diagnosis.

| Production target | Value |
|---|---|
| Seed knowledge base | **3,000+** outcome-labelled episodes (China, single hospital) |
| Core pillars | **Diagnose · Prescribe · Triage · Integrate** |
| Time from symptom entry to ranked differential | **p50 < 2 s · p95 < 5 s** |
| Prescription suggestions safety-screened | **100%** |
| Clinical decisions taken autonomously by the system | **0** (human-in-the-loop, always) |
| Target platform availability (clinical hours) | **99.9%** with graceful degradation |
| Auditability | **100%** of suggestions & decisions traceable to a model version |

> **The core principle: assist, never replace.** MediSense never makes an autonomous medical decision. Every output is a *suggestion with its reasoning attached*, presented for the licensed physician to accept, modify, or reject. The doctor's judgement is always the final authority. MediSense exists to make that judgement faster, safer, and better-informed.

**What "production-ready" means in this document.** A system is production-ready when it is (1) **clinically safe** — guardrails, fail-safe defaults, and human checkpoints are enforced in code, not policy; (2) **observable** — every suggestion, decision, latency, and drift signal is measured; (3) **operable** — it can be deployed, monitored, rolled back, and recovered by an on-call team; (4) **compliant** — it produces the evidence a medical-device and data-protection regulator requires; and (5) **maintainable** — models and rules can be improved continuously without re-engineering. This specification is organized to satisfy all five.

---

## 2. Product Vision, Scope & Non-Goals

### 2.1 Vision

MediSense is an **intelligent clinical co-pilot** that turns a hospital's own accumulated experience — the archive of *symptoms → diagnosis → treatment → outcome* it already generates and forgets — into a living assistant that gets sharper with every patient it sees. It observes a new patient's symptoms, proposes the most probable diagnoses, recommends safe treatment and prescriptions, and helps the doctor decide who to see first.

### 2.2 In scope for the production v2.0 release

The production scope is the v1.0 functional surface hardened to production grade, plus the "do-first" quick wins from the roadmap that do not require new clinical modalities:

- The four pillars (Diagnose, Prescribe, Triage, Integrate) as fully specified clinical workflows.
- Hybrid AI engine (retrieval + classifier + rules/safety) with calibrated probabilities and a full explainability surface.
- Real-time drug-safety screening with a four-level severity model and hard contraindication blocks.
- Live acuity-based triage with active escalation alerts.
- FHIR/HL7 integration with one HIS via a configurable adapter layer.
- Continuous-learning loop with structured outcome capture and active learning from physician overrides.
- Bilingual (Chinese / English) clinician web/desktop application.
- Full MLOps, observability, security, audit, and disaster-recovery foundations.

### 2.3 Roadmap-adjacent, behind feature flags (built to extend, off by default)

These are architected for from day one but are not part of the first clinical go-live; they ship on the phased plan in §25 and the roadmap themes:

Medical LLM + RAG reasoning layer, specialty ensemble models, multimodal inputs (imaging/labs/ECG), ambient voice scribe, predictive deterioration, on-prem/edge inference, federated multi-site learning, chronic-care/follow-up management, and wearables ingestion.

### 2.4 Explicit non-goals

- **Not an autonomous diagnostician or prescriber.** The system never commits a diagnosis or issues a prescription without explicit physician sign-off.
- **Not a replacement for examination, labs, or imaging.** It augments clinical assessment; it does not substitute for it.
- **Not a black box.** No suggestion is shown without its reasoning and evidence.
- **Not a system of record.** MediSense reads from and writes to the hospital's HIS/EHR; the HIS remains the legal record of care.
- **Not a patient-facing product.** v2.0 is a clinician tool. Patient/wearable surfaces are roadmap items, gated separately.
- **Not a billing, scheduling, or administrative system.** It integrates with those but does not replace them.

---

## 3. Design Principles & Production Tenets

The four founding design principles are non-negotiable and are enforced as engineering invariants, not aspirations:

1. **Physician-in-command.** AI output is always framed as a suggestion to be confirmed. The doctor accepts, edits, or overrides with one action, and every override is captured as both an audit record and a training signal. *Invariant:* no write-back to the HIS occurs on any clinical entity without an authenticated physician sign-off event.

2. **Explainable by default.** Confidence scores and the specific symptoms, past cases, and rules driving each suggestion are always one tap away. *Invariant:* every `Suggestion` object carries machine-readable evidence references; the UI cannot render a suggestion that lacks them.

3. **Safety over completeness.** When data is missing or signals conflict, MediSense says so and asks rather than guessing; it widens the differential and lowers confidence. *Invariant:* hard safety rules (allergy, contraindication, dosing limits) can veto any statistical output and are evaluated last in the pipeline.

4. **Fast at the point of care.** Sub-five-second suggestions, keyboard-light entry, glanceable layout. *Invariant:* p95 latency budgets are defined per service (§21) and are release gates.

**Additional production tenets** that govern engineering decisions:

- **Determinism where it matters.** Given the same inputs and model version, a suggestion is reproducible. Safety rules are deterministic and versioned.
- **Defense in depth.** Safety is enforced at the rules layer, the API layer, and the UI — never in a single place.
- **Graceful degradation over hard failure.** A degraded answer with a clear caveat beats a blank screen (§22.5).
- **Everything is versioned and traceable.** Models, rule sets, drug references, ontologies, and prompts all carry versions stamped onto every output.
- **No metric, no merge.** Every change names the KPI it moves and is validated in shadow/A-B before it can influence care (§14, §26).
- **Privacy by design.** Data minimization, de-identification for learning, and configurable residency are defaults, not options.

---

## 4. Users, Personas & Role Model

### 4.1 Personas

**Dr. Li Wei — Attending Physician *(Primary)***
Goal: diagnose accurately and quickly, prescribe safely, move to the next patient. Frustrations: fragmented records, fear of missing a rare condition, manual interaction checks. MediSense gives: ranked differentials with evidence, auto-screened prescriptions, full history in one view.

**Nurse Zhang — Triage & Ward Nurse *(Key)***
Goal: capture vitals and symptoms accurately, surface patients who can't wait. Frustrations: judging acuity under pressure, re-entering data. MediSense gives: a live, auto-ranked queue and structured intake.

**Pharmacist Chen — Clinical Pharmacist *(Key)***
Goal: verify every prescription is safe before dispensing. Frustrations: incomplete medication lists, time-consuming manual checks. MediSense gives: a pre-screened Rx with interaction flags and rationale to verify.

**Director Wang — Medical Administrator *(Stakeholder)***
Goal: raise care quality and consistency, manage risk, demonstrate outcomes. Frustrations: variable quality, limited diagnostic-performance visibility. MediSense gives: analytics on accuracy, override rates, fairness, and outcome trends.

**Two roles added for production** (implied by the operating model, made explicit here):

**System Administrator / Hospital IT *(Operator)***
Goal: keep MediSense connected, secure, and available. Needs: integration health dashboards, user/role provisioning, audit export, configuration of formularies and code maps.

**Clinical Safety Officer / ML Governance *(Operator)***
Goal: ensure the model stays accurate, calibrated, and fair, and that the audit and validation evidence is complete. Needs: drift and subgroup dashboards, model-release approval workflow, incident review tooling.

### 4.2 Role-based access control (RBAC) model

Access is least-privilege and role-scoped. The matrix below is the authoritative permission model enforced at the API layer.

| Capability | Physician | Nurse | Pharmacist | Admin | Safety/ML | IT/Operator |
|---|---|---|---|---|---|---|
| View triage queue | ✓ | ✓ | view | ✓ | — | — |
| Capture intake / vitals | ✓ | ✓ | — | — | — | — |
| Enter symptoms, view differential | ✓ | view | — | — | — | — |
| Confirm diagnosis | ✓ | — | — | — | — | — |
| Request Rx suggestions | ✓ | — | view | — | — | — |
| Sign & send prescription | ✓ | — | — | — | — | — |
| Pharmacist verification / hold | — | — | ✓ | — | — | — |
| Override safety flag (with reason) | ✓ | — | ✓ (dispense-level) | — | — | — |
| View analytics dashboards | summary | — | — | ✓ | ✓ | — |
| View fairness/drift dashboards | — | — | — | view | ✓ | — |
| Approve model release | — | — | — | — | ✓ | — |
| Manage users & roles | — | — | — | ✓ | — | ✓ |
| Configure formulary / code maps | — | — | ✓ (formulary) | ✓ | — | ✓ |
| Export audit log | — | — | — | ✓ | ✓ | ✓ |

> **Separation of duties.** No single role can both author a model release and approve it for clinical traffic; promotion requires the Safety/ML role, and clinical sign-off authority is reserved to licensed physicians only.

---

## 5. The Four Pillars & the Closed Learning Loop

```
   ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
   │ DIAGNOSE │  →  │ PRESCRIBE│  →  │  TRIAGE  │  →  │ INTEGRATE│
   └──────────┘     └──────────┘     └──────────┘     └──────────┘
   Rank probable    Recommend &      Score acuity     Read records,
   conditions w/    auto-screen      & order the      write back the
   confidence       medication       patient queue    agreed plan
```

| Pillar | What it does | Primary user | Tier |
|---|---|---|---|
| **Diagnosis Engine** | Compares new symptoms to the knowledge base; returns ranked differentials with probability and rationale. | Physician | Core |
| **Prescription & Safety** | Suggests treatment & drugs; screens every option against drugs, allergies, age, renal/hepatic status. | Physician, Pharmacist | Core |
| **Triage** | Continuously scores and ranks patients by criticality and urgency across the ward/clinic. | Nurse, Physician | Supporting |
| **Integration** | Connects to HIS/EHR to pull history and write back the confirmed diagnosis and Rx. | System / IT | Supporting |

> **Why the loop matters.** Diagnosis informs prescription; prescription depends on the integrated record; the record feeds triage; the doctor's confirmed outcome flows back into the knowledge base — sharpening the next diagnosis. MediSense is a **closed learning loop**, not four separate tools. The production system instruments every edge of this loop so the data flywheel is measurable (§26).

---
---

# Part II — Functional Specification

## 6. Diagnosis & Differential Probability Engine

The heart of MediSense: turning a patient's symptoms into a ranked, explained set of probable diagnoses. The physician describes or selects symptoms; the engine analyses them against the knowledge base and the patient's own record, then returns a **differential** — an ordered list of candidate conditions, each with a probability, a confidence band, and the evidence behind it.

### 6.1 Functional pipeline (what the engine does, step by step)

1. **Symptom capture & normalization.** Free-text or structured entry is mapped to a standard clinical vocabulary (SNOMED CT / ICD-10-aligned terms; ICD-10-CM and the Chinese clinical modification supported via the code-map config). Onset, duration, severity, laterality, and explicit negatives ("no fever") are captured as first-class fields. Negatives are weighted — their presence changes ranking, not just their absence.
2. **Patient-context enrichment.** Age, sex, vitals, chronic conditions, current medications, allergies, recent labs, and pregnancy status are pulled from the integrated record to condition the analysis. Missing critical context is surfaced, not silently ignored.
3. **Similarity & probabilistic matching.** The hybrid model (§12) retrieves the most similar past episodes, combines them with a learned classifier and disease-prevalence priors, and estimates the probability of each candidate condition.
4. **Ranking & calibration.** Candidates are ranked and confidence is calibrated so that a stated "78%" reflects real-world frequency (±calibration tolerance, §14.4). "Cannot-miss" critical conditions are surfaced even at low probability.
5. **Explanation assembly.** For each candidate the engine assembles supporting symptoms, contradicting signals, the count and identity of similar historical cases, typical outcomes, and the single next-best test that would most reduce uncertainty.
6. **Safety overlay.** The rules layer runs last; red-flag/do-not-miss conditions are pinned and a red-flag banner is raised regardless of statistical rank.

### 6.2 Inputs, outputs & contracts

| Input | Source | Required? | Behaviour if absent |
|---|---|---|---|
| Symptom set (coded + free text) | Clinician entry | Yes | Engine will not run without ≥1 symptom; prompts entry |
| Demographics (age, sex) | EHR via adapter | Yes | Flagged as missing; priors degrade to population default with lowered confidence |
| Vitals | EHR / nurse intake | Recommended | Triage and red-flag detection degrade gracefully; noted in evidence |
| Current medications | EHR | Required for Rx | Diagnosis runs; prescription pillar blocks until medication list is confirmed |
| Allergies | EHR | Required for Rx | Same as above; allergy screen cannot be trusted without it |
| Recent labs/imaging reports | EHR | Optional | Used when present to refine; absence lowers confidence on lab-dependent conditions |

**Primary output — the `Differential`** (see §17 for the JSON contract): an ordered list of `{condition, icd, probability, confidence band, supporting[], contradicting[], similarCases, typicalOutcomes, nextBestTest}` plus a `redFlags[]` array and a `requiresPhysicianConfirmation: true` flag that the UI must honour.

### 6.3 What the doctor sees

| Element | Description |
|---|---|
| **Ranked differential** | Each condition with a probability bar, confidence label (High / Moderate / Low / Watch), and a one-line "because…" summary. |
| **Evidence drawer** | Tap any condition to see matching symptoms, count of similar past cases, typical outcomes, contradicting findings, and counterfactuals. |
| **Next-best-test** | The single test or question that would most reduce uncertainty, with the expected confidence gain. |
| **Red-flag banner** | If symptoms match a time-critical condition (sepsis, MI, stroke, etc.), a prominent alert appears regardless of rank. |

> **Anti-anchoring by design.** The engine deliberately surfaces a **broad differential**, not a single answer, and always includes plausible "do-not-miss" alternatives — counteracting the human tendency to lock onto the first plausible diagnosis. The minimum differential breadth and the do-not-miss inclusion logic are configurable per department and are part of the safety rule set.

### 6.4 Confidence bands & their semantics

| Band | Meaning | Calibrated range (configurable) | UI treatment |
|---|---|---|---|
| **High** | Strong, consistent evidence; well-represented in KB | ≥ 0.70 | Solid bar, primary colour |
| **Moderate** | Plausible; some support, some gaps | 0.40–0.69 | Half bar, neutral colour |
| **Low** | Weak support or thin data | 0.15–0.39 | Light bar |
| **Watch** | Low probability **but do-not-miss** — pinned for safety | any, when flagged | Amber/red pin, never collapsed |

### 6.5 Worked example *(illustrative only)*

| Candidate condition | Probability | Confidence | Key supporting evidence |
|---|---|---|---|
| **Community-acquired pneumonia** | 78% | High | Fever, productive cough, focal crackles, raised CRP; 142 similar cases |
| Acute bronchitis | 41% | Moderate | Cough, low-grade fever; absence of focal signs lowers rank |
| Pulmonary embolism *(do-not-miss)* | 9% | Watch | Pleuritic pain + tachycardia; surfaced despite low probability |

*Illustrative for documentation only. Probabilities are produced per-patient and per-deployment from the trained model and are always presented for physician review.*

### 6.6 Edge cases & failure handling

- **Out-of-distribution patient.** When the patient is unlike anything in the KB (low retrieval similarity, OOD detector trips), the engine returns a widened, low-confidence differential with an explicit *"this patient is unusual — low confidence, consider escalation"* banner rather than a confident guess.
- **Conflicting signals.** The engine lowers confidence and shows the conflict in the evidence drawer rather than averaging it away.
- **Sparse symptoms.** Below a minimum information threshold, the engine asks for the highest-yield missing symptom instead of producing a ranking.
- **Classifier unavailable.** Retrieval + rules still produce a differential, clearly labelled "degraded mode — classifier offline" (§22.5).

---

## 7. Prescription & Drug-Interaction Safety

From a confirmed diagnosis to a safe, personalized treatment and prescription — with **every drug screened automatically** before it is shown. Once the doctor confirms a diagnosis, MediSense proposes a treatment plan and candidate medications drawn from how similar cases were *successfully* treated, then screens each in real time against the patient's full medication list, allergies, age, weight, and renal/hepatic function.

### 7.1 The safety screen — what every suggestion passes through

- **Drug–drug interactions.** Each candidate is checked against every current medication; contraindicated or risky combinations are blocked or flagged with severity.
- **Allergy & intolerance.** Documented allergies and prior adverse reactions are matched against the drug and its class, including cross-reactivity (e.g. penicillin → cephalosporin caution).
- **Dose for the patient.** Dosing is adjusted for age, weight, and renal/hepatic function; pediatric and geriatric limits are enforced; renal dose reduction is computed from the most recent eGFR when available.
- **Condition & context flags.** Pregnancy/lactation, comorbidities, QT-prolongation risk, and duplicate-therapy checks (two drugs of the same class) raise contextual warnings.

> **Nothing unsafe reaches the doctor unflagged.** A medication that fails a hard safety rule is never silently suggested. It is either withheld with an explanation or surfaced with a clear **severe interaction** banner and a safer alternative offered in its place.

### 7.2 Interaction severity model

| Severity | Behaviour in the UI | Override path | Example |
|---|---|---|---|
| **Contraindicated** | Blocked; cannot be signed without explicit override + reason; alternative offered. | Physician override with mandatory typed reason; logged & escalated to pharmacist | Drug + drug with life-threatening combined effect |
| **Major** | Prominent warning; must be acknowledged before prescribing. | Acknowledge + reason | Significant additive risk needing monitoring |
| **Moderate** | Inline flag with guidance (adjust dose, monitor labs). | Acknowledge | Manageable interaction with precautions |
| **Minor / info** | Subtle note, no interruption. | None | Low-significance or theoretical interaction |

**Alert-fatigue controls (production hardening).** Low-value alerts are suppressed by default and tunable per site; the system measures alert dismiss rates and override rates per rule, and the Safety Officer dashboard flags any rule with a chronic >95% dismiss rate for review. This directly addresses the classic CDS failure mode where clinicians click through every alert.

### 7.3 The prescription flow

```
Confirm Dx → Suggest plan → Auto-screen → Doctor decides → Sign & send → Pharmacist verify
(accept a    (treatment &   (each option   (accept, swap,   (Rx written     (independent
 diagnosis)   drug options)  vs. record)    or adjust;        to record &      second check
                                            override logged)  routed to Rx)    before dispense)
```

### 7.4 Drug reference & formulary

- Screening uses a versioned **drug-interaction reference** and a site-configurable **formulary**; both carry version stamps recorded on every screened suggestion.
- The reference is updatable from authoritative sources without a code release; updates pass a validation gate before activation (§13.4, §14).
- Dosing logic supports weight-based, BSA-based, and renal-adjusted regimens; pediatric and geriatric bounds are enforced as hard rules.

### 7.5 Edge cases

- **Incomplete medication list.** Prescription pillar is blocked with a clear "medication list unverified" state — the allergy/interaction screen cannot be trusted otherwise.
- **External drug reference unavailable.** The system falls back to the local interaction set and labels the screen "reduced coverage — external reference offline"; contraindication blocks from the local set still apply (§22.5).
- **Override of a contraindication.** Always permitted only with a typed reason, always logged immutably, always surfaced to the verifying pharmacist, and counted in safety telemetry.

---

## 8. Triage & Patient Prioritization

Across a busy ward or clinic, MediSense maintains a live, ordered queue ranked by an **acuity score** blending how critical and how urgent each patient's condition is — so the care team always knows who needs attention first.

### 8.1 What feeds the acuity score

- Vital signs and early-warning thresholds (respiratory rate, SpO₂, blood pressure, heart rate, temperature; mappable to NEWS2-style scoring per site).
- Severity of the top candidate diagnoses and presence of any do-not-miss red flags.
- **Trend** — is the patient deteriorating or stable since the last reading?
- Time waiting, age, and known high-risk comorbidities.

### 8.2 Scoring model & transparency

The acuity score is a transparent, rule-weighted composite (not a black box): each contributing factor and its weight is shown on demand, and the score recomputes whenever new vitals, results, or symptoms arrive. Weights are site-configurable and versioned with the rule set so that any change to triage behaviour is auditable.

### 8.3 Priority bands

- **CRITICAL** — Immediate; possible life threat; pushed to top, alert raised.
- **URGENT** — See soon; significant risk or deteriorating trend.
- **ROUTINE** — Stable; standard queue order.

Bands are visually unmistakable (colour **and** label) and re-rank automatically.

> **Escalation, not just ordering.** When a patient crosses into **Critical**, MediSense does more than re-sort the list — it raises an **active alert** to the responsible clinician (in-app, and via configurable secondary channel) so a deteriorating patient is never missed because no one was looking at the screen. Escalation alerts require acknowledgement and are logged with time-to-acknowledge.

### 8.4 The triage board *(illustrative)*

| # | Patient | Chief complaint | Key vitals | Top suggestion | Priority |
|---|---|---|---|---|---|
| 1 | Patient A, 67M | Chest pain, sweating | HR 118, BP 92/60 | ACS — do-not-miss | CRITICAL |
| 2 | Patient B, 24F | Severe abdominal pain | Temp 39.1°C | Appendicitis | URGENT |
| 3 | Patient C, 41M | Cough, mild fever | SpO₂ 97% | Bronchitis | ROUTINE |

*Illustrative. Scores and bands are computed per-patient from live data and clinical rules and are always advisory to the care team.*

### 8.5 Edge cases

- **Stale vitals.** Vitals older than a configurable threshold are visually marked and down-weighted; the board never implies confidence it doesn't have.
- **Alert storm.** Escalation alerts are de-duplicated and rate-limited per patient; a single deterioration does not produce repeated identical pages.
- **Tie-breaking.** Equal acuity is ordered by trend, then waiting time — deterministic and explainable.

---

## 9. Hospital & EHR Integration

MediSense is only as good as the data it sees. It connects to the hospital's existing systems to pull a complete, current patient picture — and to write the confirmed diagnosis and prescription back where the rest of the care team can act on it.

### 9.1 What it reads and writes

**Reads from the hospital record**

- Demographics, allergies, problem list, chronic conditions.
- Current and past medications (the basis of interaction checks).
- Recent vitals, lab results, and imaging reports.
- Encounter and visit history.

**Writes back (after physician sign-off only)**

- The confirmed diagnosis and coded problem.
- The signed prescription, routed to pharmacy.
- Ordered tests and follow-up plan.
- An audit trail of what was suggested vs. chosen.

### 9.2 How it connects

- **Standards-based interfaces.** Primary integration via **HL7 FHIR** resources (`Patient`, `Condition`, `MedicationRequest`, `Observation`, `AllergyIntolerance`, `ServiceRequest`) with HL7 v2 messaging where the hospital's HIS requires it.
- **Adapter layer for legacy HIS.** A configurable adapter maps each hospital's local data formats and code systems to the MediSense **canonical model**, so onboarding a new site is configuration, not re-engineering. The adapter is the single place site-specific differences live.
- **China-first localization.** The first deployment integrates with the partner hospital's HIS and is tuned to local terminology, drug formularies, and coding conventions; these are swappable configuration for future sites.
- **Security at the boundary.** All exchange is encrypted, authenticated (mutual TLS + scoped service credentials), scoped to the minimum data needed, and fully logged. Data residency follows the hospital's and jurisdiction's requirements.

### 9.3 Integration patterns & resilience

- **Sync reads** for the patient-open path (low latency, cached per encounter).
- **Event subscriptions** (FHIR Subscription / HL7 feeds) for new vitals and lab results so the differential and triage board update without polling.
- **Idempotent, transactional write-back** with retry and dead-letter handling: a sign-off that fails to write is retried and surfaced to the clinician; it is never silently dropped.
- **Reconciliation job** verifies that every signed decision has a corresponding HIS write, alerting on divergence.

> **Designed to fit in, not rip and replace.** MediSense layers on top of the systems a hospital already runs. The physician keeps their existing workflow; MediSense adds intelligence inside it rather than asking the institution to migrate.

---

## 10. End-to-End User Flows

### 10.1 Primary consultation flow

A single consultation, end to end — showing where MediSense assists and where the physician stays firmly in command.

1. **Patient arrives & is registered.** Nurse captures chief complaint and vitals at intake. MediSense immediately places the patient in the triage queue with a provisional priority band.
2. **Doctor opens the patient.** A unified patient view loads: integrated history, current medications, allergies, recent results — no hunting across systems.
3. **Symptoms entered.** The doctor enters or refines symptoms. The engine returns a ranked differential within seconds, red flags first.
4. **Doctor reviews the evidence.** They open the evidence drawer on leading candidates, check supporting and contradicting signals, and see the next-best test.
5. **Tests ordered (optional).** If confirmation is needed, tests are ordered through the integration; results flow back and update the differential automatically.
6. **Diagnosis confirmed.** The doctor accepts a diagnosis (or records their own). The choice — including any override of the AI's top suggestion — is logged for learning.
7. **Treatment & prescription.** MediSense proposes a plan and medications, each pre-screened. The doctor adjusts and signs.
8. **Plan written back.** The signed diagnosis, prescription, and follow-up are written to the hospital record and routed to pharmacy and the care team.
9. **Outcome & feedback.** Recovery feedback and outcome are captured later and fed back into the knowledge base, improving suggestions for the next similar patient.

> **The human checkpoint is non-negotiable.** Steps 6 and 7 — confirming the diagnosis and signing the prescription — **always require explicit physician action**. MediSense can prepare everything, but the doctor commits it.

### 10.2 Secondary flows (specified for production completeness)

- **Pharmacist verification flow.** Signed Rx appears in the pharmacist queue with all flags and override reasons; pharmacist verifies, queries, or holds; a hold notifies the prescriber.
- **Nurse intake & re-vitals flow.** Nurse records vitals; a deteriorating reading can re-band the patient and raise escalation without a physician action.
- **Outcome-capture flow.** At discharge/follow-up, a structured outcome (improved/unchanged/worsened, readmission, scales) is captured with minimal friction and attached to the episode.
- **Override-review flow.** Safety/ML officer reviews disagreement and override cases as the highest-value learning and audit signal (§14.5).
- **Degraded-mode flow.** When a service is down, the UI states which capability is reduced and what remains trustworthy (§22.5).

---

## 11. Screen-by-Screen UX Specification

Wireframe-level layouts of the screens a physician lives in. The design language favours clarity, glanceability, and keeping AI output visibly framed as a suggestion. Each screen lists purpose, key interactions, and **all states** (a production requirement so no state is left unhandled).

### A · Triage Board — the daily home screen

```
┌────────────────────────────────────────────────────────────┐
│ MediSense · Triage Board — Internal Medicine   Dr. Li · 12  │
├──────────────┬─────────────────────────────────────────────┤
│ FILTERS      │  ● CRITICAL 2   ● URGENT 4   ● ROUTINE 6     │
│  □ Dept      │  ┌─────────────────────────────────────────┐ │
│  □ Priority  │  │ 1 · Patient A · ACS         [CRITICAL]   │ │
│  □ Status    │  ├─────────────────────────────────────────┤ │
│              │  │ 2 · Patient B · Appendicitis  [URGENT]   │ │
│ DEPARTMENTS  │  ├─────────────────────────────────────────┤ │
│  □ IM □ ER   │  │ 3 · Patient C · Bronchitis    [ROUTINE]  │ │
└──────────────┴─────────────────────────────────────────────┘
Auto-sorted by acuity. Critical rows pulse and raise an alert.
```

- **Purpose:** the clinician's home; who needs attention now.
- **Key interactions:** filter by department/priority/status; click a row to open the patient; acknowledge a critical alert.
- **States:** empty (no patients), loading, live-updating as vitals arrive, stale-data warning, degraded (triage scoring offline → manual order with banner), alert-active.

### B · Patient & Diagnosis View — the consultation screen

```
┌────────────────────────────────────────────────────────────┐
│ Patient A · 67M · MRN 0098-2231        Allergies: Penicillin│
├──────────────┬─────────────────────────────────────────────┤
│ HISTORY &    │ ⚠ RED FLAG: possible ACS — assess now        │
│ MEDS         │                                              │
│  • COPD      │ DIFFERENTIAL                                 │
│  • HTN       │ ▸ Acute coronary syndrome   72% [High]   ›   │
│              │ ▸ Unstable angina           38% [Mod]    ›   │
│ CURRENT DRUGS│ ▸ Aortic dissection (DNM)    6% [Watch]  ›   │
│  • Aspirin   │                                              │
│  • Metformin │ Each row: probability bar · confidence ·     │
│              │ "because…" · evidence ›                      │
└──────────────┴─────────────────────────────────────────────┘
```

- **Purpose:** the single place a doctor diagnoses; history on the left, AI differential on the right.
- **Key interactions:** enter/refine symptoms; expand any candidate's evidence drawer; accept a diagnosis; order a test.
- **States:** awaiting symptoms, computing, results, results-updated-after-new-data, low-confidence/OOD banner, missing-context warning, degraded (classifier offline).

### C · Prescription & Safety

```
┌──────────────────────────────────┐
│ Prescribe — CAP        [screened] │
├──────────────────────────────────┤
│ ▸ Amoxicillin 500mg               │
│   ⚠ Penicillin allergy → blocked  │
│      Alternative: Azithromycin ✓  │
│ ▸ Azithromycin 500mg  [cleared]   │
│ Every drug pre-checked; severe    │
│ flags block until resolved.       │
└──────────────────────────────────┘
```

- **Purpose:** convert a confirmed diagnosis into a safe prescription.
- **Key interactions:** accept/swap/adjust a drug; acknowledge or override a flag (with reason); sign & send.
- **States:** cleared, moderate-flag, major-flag (must acknowledge), contraindicated (blocked), medication-list-unverified (blocked), external-reference-offline (reduced coverage), signed/sent.

### D · Evidence Drawer

```
┌──────────────────────────────────┐
│ Why pneumonia? 78%      142 cases │
├──────────────────────────────────┤
│ Supports: fever · cough ·         │
│           crackles · ↑CRP         │
│ Against:  no pleuritic pain       │
│ Next-best test: chest X-ray       │
│                 (+confidence)     │
└──────────────────────────────────┘
```

- **Purpose:** make every suggestion auditable in one tap.
- **Key interactions:** view supporting/contradicting evidence; see similar historical cases and outcomes; view counterfactuals ("if this symptom were absent, rank would drop to…"); jump to the next-best test.

### E · Administrator & Safety dashboards *(production addition)*

- **Admin analytics:** accuracy (Top-1/Top-3), acceptance/override rates, time-to-decision, throughput, outcome trends by department.
- **Safety/ML dashboards:** calibration, subgroup/fairness gaps, drift, alert dismiss rates, model-version performance, release approval queue.
- **Integration health (IT):** adapter status, write-back success/reconciliation, queue depths, reference/formulary versions.

> **One consistent interaction model.** Across every screen, AI output uses the same visual grammar: a coloured confidence cue, a plain-language reason, and an always-available "show evidence." The doctor learns to trust it because it always shows its work.

---
---

# Part III — Technical Architecture

## 12. AI / ML Architecture

MediSense uses a **hybrid architecture** — combining case-based retrieval, machine-learned classification, and an explicit clinical rules layer. No single technique is trusted alone; each covers the others' blind spots, and the rules layer guarantees safety.

### 12.1 The three layers

1. **Retrieval (case-based).** Each past episode is embedded into a vector representation of its symptoms and context. A new patient retrieves the most similar historical cases — the engine reasons from real precedent and can always point to "patients like this one."
2. **Learned classifier.** A supervised model trained on the labelled episodes estimates the probability of each condition from the symptom/context vector, capturing patterns beyond any single neighbour and calibrating the final probabilities.
3. **Clinical rules & safety.** An explicit, expert-curated rules layer enforces red-flag detection, interaction/allergy blocks, and dosing limits. Rules can hard-override the statistical layers — safety is never left to probability alone.

### 12.2 The reasoning pipeline

```python
# Conceptual flow — symptoms in, explained suggestions out
patient   = enrich(symptoms, ehr_record)               # context: age, meds, labs, allergies
neighbors = retrieve(patient, knowledge_base)           # most similar past episodes (ANN)
probs     = classify(patient, neighbors)                # calibrated disease probabilities
probs     = apply_rules(probs, patient)                 # red flags + do-not-miss surfacing
dx        = rank_and_explain(probs, neighbors)          # ordered differential + evidence

rx = recommend_treatment(dx, knowledge_base)            # weighted by recovery outcome
rx = safety_screen(rx, patient.meds, patient.allergies) # interactions, dose, allergy

return dx, rx   # presented to physician for confirmation — never auto-committed
```

### 12.3 Why hybrid, not a single black box

| Property | How the architecture delivers it |
|---|---|
| **Explainability** | Retrieval gives "cases like this"; rules give named reasons. Every suggestion traces to evidence. |
| **Safety** | The rules layer can override statistics — hard constraints (allergy, contraindication) always win. |
| **Cold-start tolerance** | For rare conditions with few examples, retrieval + rules still function where a pure classifier would be unreliable. |
| **Calibration** | Probabilities are calibrated against observed frequencies, so confidence is honest. |
| **Improvability** | New labelled episodes update retrieval and classifier without re-engineering the rules. |
| **Degradability** | Layers are independent services; losing one yields a labelled, reduced answer rather than an outage. |

> **Handling uncertainty honestly.** When evidence is thin or signals conflict, the engine widens its differential, lowers stated confidence, and explicitly asks for the missing information rather than projecting false certainty.

### 12.4 Component model & technology choices *(reference design)*

| Component | Responsibility | Reference technology | Notes |
|---|---|---|---|
| **Embedding service** | Encode symptom/context into vectors | Clinical-domain encoder (text + structured features) | Versioned; re-embedding job on model change |
| **Vector index** | Approximate nearest-neighbour retrieval | HNSW / IVF-PQ (e.g. FAISS / Milvus) | Sharded, periodically re-indexed; embeddings cached |
| **Classifier** | Calibrated condition probabilities | Gradient-boosted + neural ensemble | Calibrated (temperature/Platt/isotonic); subgroup-gated |
| **Calibrator** | Map raw scores → honest probabilities | Isotonic / temperature scaling | Re-fit per release; monitored for drift |
| **OOD detector** | Flag out-of-distribution patients | Distance-to-manifold / energy score | Triggers low-confidence/escalation path |
| **Rules engine** | Red flags, interactions, dosing, do-not-miss | Declarative, versioned rule set | Deterministic; evaluated last; hard veto |
| **Triage scorer** | Acuity composite | Rule-weighted, transparent | Recomputes on new data |
| **Treatment recommender** | Outcome-weighted plan/drug suggestions | Retrieval over outcome-labelled episodes | Feeds safety screen |

### 12.5 Extensibility hooks (roadmap-ready, flagged off)

The pipeline exposes seams so roadmap capabilities slot in without re-architecture: a **RAG/LLM reasoning step** (grounded, citation-required, rules-vetoed) between `rank_and_explain` and presentation; **specialty sub-model routing** keyed on department before `classify`; **multimodal feature fusion** (imaging/labs/ECG encoders) into the patient vector; and a **cascade** that escalates from a distilled fast model to the heavy model only when uncertain. Each hook is dark-shipped behind a flag and must pass the same safety gates before it can influence care.

### 12.6 Safety invariants of the engine

- The rules/safety layer is evaluated **last** and can override any upstream output.
- Every LLM/generative claim (when that layer is enabled) must cite a retrieved source or be suppressed.
- No engine path can emit a suggestion without evidence references attached.
- The engine never auto-commits; it returns suggestions with `requiresPhysicianConfirmation: true`.

---

## 13. Knowledge Base & Continuous Learning

MediSense begins with a seed knowledge base of **3,000+ diagnostic episodes** and grows with every consultation. Each episode is a complete, outcome-labelled record — the unit the whole system learns from.

### 13.1 Anatomy of a knowledge-base episode

1. **Symptoms & presentation.** Structured symptoms with onset, severity, and negatives, plus patient context at the time of the visit.
2. **Doctor's diagnosis.** The confirmed condition(s), coded to a standard vocabulary — the ground-truth label.
3. **Treatment & prescription.** The solution the doctor chose: procedures, medications, doses, follow-up.
4. **Recovery feedback.** How well the patient improved — the outcome signal that tells the model which solutions actually worked.

> **Outcome is the secret ingredient.** Most systems learn "symptoms → diagnosis." MediSense also learns "treatment → **recovery**." Weighting suggestions by what genuinely led to good outcomes is what lets it recommend not just a plausible plan, but a plan that has *worked* for patients like this one.

### 13.2 The continuous-learning loop

```
CAPTURE → CURATE → LEARN → EVALUATE → SERVE
new       validate,  update    measure     sharper
episode   de-id,     index &   accuracy &  suggestions
stored    code       model     calibration for next patient
```

### 13.3 Active learning (production priority)

Not every episode teaches equally. The pipeline prioritizes labelling and learning on **disagreement cases** (AI vs. physician differed) and **high-uncertainty/OOD cases** — these teach the most per example, which is critical when data is scarce. Physician overrides become the single most valuable training signal and are routed to the Safety/ML review queue.

### 13.4 Automated data-quality pipeline

Every candidate episode passes automated validation **before** it can enter the KB: schema/format validation, de-duplication, outlier and label-consistency checks, code-mapping verification, and de-identification. Bad data is quarantined for human review, never silently admitted. *Rationale: garbage-in is the fastest way to lose clinician trust.*

### 13.5 Quality & governance of the data

- **Human-validated labels:** diagnoses and outcomes come from physicians, not inferred guesses.
- **Bias monitoring:** performance tracked across age, sex, condition, and department groups to catch skew before it harms care.
- **Versioned KB snapshots:** every model is trained against an immutable, hash-identified KB snapshot for reproducibility.
- **De-identification:** data used for learning is governed and minimized per §18.
- **Provenance:** every episode records its source, curation steps, and the consent/governance basis under which it may be used for learning.

---

## 14. MLOps, Model Lifecycle & Evaluation

Production AI is only safe if it can be evaluated, shipped, monitored, and rolled back with discipline. This section makes the model lifecycle operational.

### 14.1 Lifecycle stages

```
DATA SNAPSHOT → TRAIN → OFFLINE EVAL (gates) → SHADOW → A/B (optional) → CANARY → FULL → MONITOR → (ROLLBACK)
```

- **Train** against an immutable KB snapshot; all hyperparameters, data hash, and code commit recorded.
- **Offline eval** on a held-out test set; must pass accuracy, calibration, and subgroup gates (§14.4) or it cannot proceed.
- **Shadow** against live traffic — produces suggestions invisibly, compared to the production model and to physician decisions; no patient impact.
- **A/B / canary** — gradual exposure to a slice of clinicians with automatic guardrail monitoring.
- **Full rollout** only after canary holds; **one-click rollback** to the previous version is always available.

### 14.2 Versioning & traceability

Every model, rule set, calibrator, drug reference, ontology, and (when enabled) prompt template carries a semantic version. Every `Suggestion` is stamped with the exact versions that produced it, so any output is reproducible and auditable years later.

### 14.3 Shadow & A/B evaluation

New models run in shadow mode against real traffic before they can influence the UI; UX changes are A/B tested. This validates every change on real data before it can affect care — the operational form of "no metric, no merge."

### 14.4 Release gates (a model cannot ship unless all pass)

| Gate | Requirement |
|---|---|
| **Top-1 / Top-3 accuracy** | ≥ current production on the held-out set (no regression) |
| **Calibration** | Calibration error within tolerance; no systematic over-confidence |
| **Subgroup/fairness** | No subgroup (age/sex/condition/dept) accuracy or calibration gap beyond threshold |
| **Long-tail** | Rare-condition recall not regressed |
| **Safety** | 100% of do-not-miss red-flag test cases caught; zero contraindication-block regressions |
| **Latency** | p95 within budget on representative hardware |
| **Reproducibility** | Re-train from snapshot reproduces metrics within variance band |

### 14.5 Production monitoring & drift detection

Live monitoring of accuracy (where ground truth arrives), calibration, latency, acceptance/override rates, alert dismiss rates, and input/data drift. Alerts fire on degradation; sustained drift triggers a retraining or rollback decision. Problems are caught from telemetry, not patient complaints.

### 14.6 Bias & fairness auditing

Continuous, automated subgroup-performance dashboards with alerting when any group's accuracy or calibration drifts. Fairness is a release gate **and** a runtime monitor — catching inequity before it harms patients and providing the evidence regulators expect.

---

## 15. Data Model & Canonical Schema

A layered architecture keeps the clinical interface fast, the AI services independently scalable, and the integration with hospital systems cleanly separated behind an adapter that maps everything to a **canonical model**.

### 15.1 Core data entities

| Entity | Key attributes |
|---|---|
| **Patient** | ID, demographics, allergies, problem list, chronic conditions (from EHR via adapter) |
| **Encounter** | Visit context, presenting complaint, vitals, attending clinician, timestamp |
| **SymptomSet** | Coded symptoms with onset, severity, duration, laterality, explicit negatives |
| **DiagnosisEpisode** | Symptoms · doctor's diagnosis · treatment/Rx · recovery outcome — the KB unit |
| **Medication** | Drug, class, dose, route; current & historical, for interaction screening |
| **Suggestion** | Ranked differential / Rx options with probability, confidence, evidence refs, model versions |
| **Decision** | What the doctor confirmed vs. what was suggested, with override reason & audit |
| **AcuityScore** | Computed priority band, contributing factors & weights, timestamped trend |
| **AuditEvent** | Immutable record of every view, suggestion, override, and sign-off |
| **OutcomeRecord** | Structured recovery signal: scale, readmission flag, follow-up status |

> **The Decision entity is doubly valuable.** By recording suggestion *and* the doctor's final choice, MediSense builds both an **audit trail** for safety/governance and a **training signal** — every physician override is a lesson the system learns from.

### 15.2 Canonical model & code systems

- All clinical concepts are stored in the canonical model and coded to SNOMED CT / ICD-10 (with the Chinese clinical modification supported); the adapter maps each site's local codes in and out.
- An **ontology/knowledge-graph layer** captures relationships (symptom hierarchies, drug classes, body systems) so the engine reasons over structure, not flat codes — improving similarity, explanations, and localization.

### 15.3 Data stores (reference design)

| Store | Purpose | Reference technology |
|---|---|---|
| **Operational DB** | Encounters, decisions, suggestions, audit | PostgreSQL (row-level security, append-only audit table) |
| **Vector index** | Episode embeddings for retrieval | Milvus / FAISS (sharded) |
| **Knowledge base store** | Outcome-labelled episodes + snapshots | Versioned object store + relational metadata |
| **Drug/formulary reference** | Interaction & dosing data | Versioned reference DB, updatable out-of-band |
| **Audit log** | Immutable, tamper-evident events | Append-only / WORM storage with integrity hashing |
| **Cache** | Per-encounter context & differential cache | Redis (encrypted, short TTL) |

### 15.4 Data retention & residency

Retention periods are configurable per jurisdiction; the audit log is retained per regulatory minimums; learning data is de-identified and governed; all stores honour configurable **data residency** so patient data does not leave the permitted region.

---

## 16. System & Infrastructure Architecture

### 16.1 Logical architecture

```
┌──────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                        │
│  Clinician web/desktop app — triage, patient view,        │
│  diagnosis & prescription surfaces (bilingual)            │
├──────────────────────────────────────────────────────────┤
│  APPLICATION & API LAYER                                  │
│  Auth · session · request routing · write-back · audit    │
├──────────────────────────────────────────────────────────┤
│  AI SERVICES                                              │
│  Retrieval · Classification · Rules/Safety · Triage score │
├──────────────────────────────────────────────────────────┤
│  DATA & KNOWLEDGE LAYER                                   │
│  Episode KB · vector index · drug-interaction reference · │
│  canonical patient model · audit store                   │
├──────────────────────────────────────────────────────────┤
│  INTEGRATION ADAPTER                                      │
│  FHIR / HL7 connectors → hospital HIS / EHR               │
└──────────────────────────────────────────────────────────┘
```

- **Presentation layer.** Clinician web/desktop app — triage board, patient view, diagnosis & prescription surfaces. Built for speed and glanceability; bilingual and localizable from day one.
- **Application & API layer.** Orchestrates a consultation: authentication, session, request routing to AI services, write-back, and audit logging. Enforces RBAC and all safety invariants at the boundary.
- **AI services.** Independent, separately deployable and horizontally scalable services for retrieval, classification, rules/safety, and triage scoring.
- **Data & knowledge layer.** Episode KB, vector index, drug-interaction reference, canonical patient model, and the immutable audit store.
- **Integration adapter.** FHIR/HL7 connectors mapping each hospital's HIS to the canonical model — the single place site-specific differences live.

### 16.2 Architectural style & cross-cutting decisions

- **Service-oriented, event-augmented.** Core request/response for the consultation path; an **event-driven** backbone for new vitals/labs and for decoupling slow steps (e.g. external drug-reference lookups) so they never block the UI.
- **Asynchronous, non-blocking UI.** Diagnosis, safety screening, and triage scoring are decoupled; a slow dependency degrades gracefully instead of freezing the screen.
- **Stateless application services** behind a load balancer; session state in the encrypted cache; horizontal autoscaling per service load.
- **Caching & precomputation.** Patient-context embeddings precomputed at encounter open; differential results cached within an encounter so symptom refinements are incremental, not full recomputes — tightening perceived latency toward instant.
- **Deployment topology options.** Cloud, hospital private cloud, or **on-prem/edge inference** (made feasible by distilled models) so data never leaves the hospital where residency rules require it.
- **Multi-tenant, multi-region foundation.** Tenant isolation, per-region residency, and a localization engine for language, terminology, and formularies — turning the single-site pilot into a repeatable platform.

### 16.3 Performance engineering levers (built in, tunable)

Model distillation + cascade (fast model for the common case, heavy model only when uncertain); ANN index tuning, sharding, periodic re-indexing, and embedding caching; per-encounter result caching; and graceful-degradation tiers (§22.5). These keep latency sub-second for common cases and cost-per-consultation bounded as the KB grows from thousands to millions of episodes.

---

## 17. API Surface & Integration Contracts

The application layer exposes a clean internal API consumed by the clinician app and a standards-based boundary to the hospital. Shapes below define intent; they are versioned contracts, not frozen forever.

### 17.1 Internal clinical API (illustrative)

| Endpoint | Method | Purpose |
|---|---|---|
| `/encounters/{id}/symptoms` | `PUT` | Submit/refine the symptom set for an encounter |
| `/encounters/{id}/differential` | `GET` | Retrieve ranked differential with evidence |
| `/encounters/{id}/diagnosis` | `POST` | Physician confirms a diagnosis (logs decision) |
| `/encounters/{id}/prescription` | `POST` | Request screened treatment & drug suggestions |
| `/prescriptions/{id}/sign` | `POST` | Physician signs; triggers write-back to HIS |
| `/prescriptions/{id}/verify` | `POST` | Pharmacist verification / hold |
| `/triage/queue` | `GET` | Live, acuity-ranked patient queue |
| `/encounters/{id}/outcome` | `POST` | Capture structured recovery outcome |
| `/episodes` | `POST` | Capture a completed episode for the knowledge base |
| `/audit/events` | `GET` | Query the immutable audit trail (scoped by role) |

### 17.2 API conventions (production)

- **Versioned** (`/v2/…`), JSON over HTTPS, OAuth2/OIDC bearer tokens, RBAC-scoped per §4.2.
- **Idempotency keys** on all write endpoints (`sign`, `diagnosis`, `episodes`) to make retries safe.
- **Every response stamps `modelVersion`, `ruleSetVersion`, `drugRefVersion`** where applicable.
- **`requiresPhysicianConfirmation`** is returned on all suggestion payloads and enforced server-side on commit.
- **Standard error envelope** with machine-readable codes and a `degradedMode` indicator when a service is in fallback.
- **Rate limiting & audit** on every call; PII-minimized payloads.

### 17.3 Example: differential response *(illustrative)*

```json
{
  "encounterId": "enc_0098",
  "modelVersion": "dx-2026.06.1",
  "ruleSetVersion": "rules-2026.05.2",
  "differential": [
    {
      "condition": "Community-acquired pneumonia",
      "icd": "J18.9",
      "probability": 0.78,
      "confidence": "high",
      "supporting": ["fever", "productive_cough", "focal_crackles", "raised_crp"],
      "contradicting": ["no_pleuritic_pain"],
      "similarCases": 142,
      "typicalOutcomes": {"improved": 0.91, "readmission_30d": 0.04},
      "nextBestTest": "chest_xray",
      "counterfactual": {"remove": "focal_crackles", "newProbability": 0.55}
    }
  ],
  "redFlags": [],
  "ood": false,
  "requiresPhysicianConfirmation": true
}
```

### 17.4 Hospital boundary (FHIR resources)

| FHIR resource | Direction | Use |
|---|---|---|
| `Patient` | Read | Demographics, identifiers |
| `AllergyIntolerance` | Read | Allergy screening |
| `MedicationRequest` | Read / Write | Current meds in; signed Rx out |
| `Observation` | Read | Vitals & lab results |
| `Condition` | Write | Confirmed, coded diagnosis |
| `ServiceRequest` | Write | Ordered tests / follow-up |

### 17.5 Integration contract guarantees

- **Write-back is transactional and idempotent**, with retry, dead-letter, and a reconciliation job verifying every signed decision reached the HIS.
- **Event subscriptions** deliver new vitals/labs to update the differential and triage board in near-real-time.
- **Adapter conformance tests** validate each new site's mappings before go-live.

---
---

# Part IV — Production Readiness

## 18. Security, Privacy & Data Governance

A clinical system handling patient data must earn trust before anything else. Security, privacy, and clinical safety are built into the architecture — not added afterward.

### 18.1 Data protection

- **Encryption everywhere.** TLS 1.2+ in transit (mutual TLS at the HIS boundary); AES-256 at rest across all stores and backups; key management via an HSM/KMS with rotation.
- **Role-based access control.** Least-privilege per §4.2; row-level security in the operational DB; clinicians see only what their role permits.
- **Data minimization.** Only the fields needed for a task are exchanged or stored; payloads are PII-minimized.
- **De-identification for learning.** Data used to train/evaluate models is de-identified and governed; re-identification keys are segregated and access-controlled.
- **Configurable data residency.** All stores honour a per-deployment residency policy so patient data stays within the permitted jurisdiction.
- **Secrets management.** No credentials in code or config; injected at runtime from a secrets manager; short-lived service tokens.

### 18.2 Identity, authentication & authorization

- OAuth2 / OIDC SSO integrated with the hospital identity provider; MFA for privileged roles.
- Clinician identity bound to every action; sign-off events carry a cryptographically verifiable actor.
- Session timeouts and re-authentication for high-risk actions (prescription sign-off, override).

### 18.3 Accountability & audit

- **Full audit trail** of every suggestion, view, override, and sign-off — immutable and tamper-evident (append-only/WORM with integrity hashing).
- **Versioned models** — every output traceable to the exact model/rule/reference versions.
- **Clear attribution** — actions tied to an authenticated clinician; overrides carry typed reasons.
- **Exportable** audit evidence for regulators and internal review.

### 18.4 Clinical safety guardrails (enforced in code)

- **Human-in-the-loop, always.** No diagnosis recorded and no prescription issued without explicit physician confirmation. The system cannot act autonomously on a patient.
- **Fail-safe defaults.** On low confidence, missing data, or conflicting signals, MediSense defers to the clinician and asks — it never fills gaps with confident guesses.
- **Hard safety rules win.** Allergy and contraindication blocks override any statistical suggestion; unsafe options are withheld or loudly flagged.
- **Continuous monitoring.** Accuracy, calibration, override rates, and subgroup performance are monitored so drift or bias is caught early.

### 18.5 Application & infrastructure security

- Secure SDLC: dependency scanning, SAST/DAST, secret scanning, and security review on every change.
- Network segmentation between presentation, application, AI, and data layers; least-privilege service-to-service auth.
- Penetration testing and threat modelling before go-live and on a recurring cadence.
- Vulnerability management with defined remediation SLAs by severity.

### 18.6 Privacy governance

- A documented lawful basis and consent model for data used in care vs. data used for learning.
- Data Protection Impact Assessment maintained; data-subject request handling defined.
- Alignment with applicable data-protection law in each market (PIPL and the data-security regime in China for the first deployment; GDPR-equivalent controls as a portable baseline).

---

## 19. Regulatory & Clinical Validation

### 19.1 Regulatory posture

MediSense is positioned as **clinical decision support**, keeping the licensed physician as the decision-maker. This posture — human-in-the-loop, transparent, non-autonomous — is the foundation of its regulatory classification and is enforced technically, not just stated.

### 19.2 First-market path (China / NMPA)

- Assemble the medical-device documentation pathway for **NMPA**, including intended-use statement, risk classification, clinical-evaluation evidence, and a quality-management posture.
- Build the regulator's evidence requirements into the product: model versioning, audit trails, validation datasets, and post-market surveillance hooks already exist by design.

### 19.3 Clinical validation track (start early — it gates scale)

- **Retrospective validation** on held-out, outcome-labelled data with the §14.4 gates.
- **Prospective, silent (shadow) validation** in the pilot hospital before any influence on care.
- **Supervised live use** with measured accuracy, safety catches, and acceptance before broadening.
- A defined **clinical evidence dossier** accumulated across phases, reusable for each new market.

### 19.4 Quality management & change control

- Documented change control for models, rules, and references; every clinical-impacting change is reviewed, gated, versioned, and reversible.
- Post-market surveillance: monitor real-world performance and adverse-event signals; defined process to investigate, correct, and report.

### 19.5 Localization for new markets

Each market has its own medical-device and data-protection requirements. The architecture keeps language, terminology, formularies, and regulatory evidence as swappable configuration, so entering a new market is a localization + validation playbook rather than a rebuild.

---

## 20. Design System

A calm, clinical, high-contrast visual system built for fast reading at the point of care, where colour carries meaning — never decoration.

### 20.1 Colour & meaning

| Token | Hex | Meaning |
|---|---|---|
| Teal · Primary | `#0F766E` | Brand, navigation, AI confidence-positive |
| Indigo · Action | `#4F46E5` | Prescription & interactive actions |
| Emerald · Safe | `#059669` | Cleared checks, routine priority, good outcomes |
| Amber · Caution | `#D97706` | Urgent priority, moderate warnings |
| Red · Critical | `#DC2626` | Red flags, contraindications, critical acuity |
| Ink · Text | `#0F172A` | Primary text and high-contrast labels |

### 20.2 Typography

- A single, highly legible sans-serif family across the interface.
- Strict hierarchy: page title → section → card title → body → caption.
- Numbers (vitals, probabilities, doses) get tabular treatment for fast scanning.

### 20.3 Principles in the interface

- **Glanceability.** Priority and confidence readable in under a second from across a room. Status shown by colour **and** label, never colour alone — accessible to colour-vision deficiency.
- **Suggestion framing.** AI output always carries a confidence cue, a plain-language reason, and an "accept / edit / reject" control — visually distinct from confirmed clinician input.
- **Progressive disclosure.** The summary is always visible; evidence and detail are one tap away. The doctor controls depth.
- **Low-friction entry.** Keyboard-light, autocomplete-driven symptom and drug entry; one-tap accept of a full suggested plan; "clicks-per-patient" tracked and driven down as a metric.
- **Consistency.** A shared component library and design tokens enforce the same grammar across every screen and both languages.

*Bilingual interface (Chinese / English) is a first-class requirement for the China deployment; all components are built for localization from day one.*

---

## 21. Non-Functional Requirements

| Area | Target / Requirement |
|---|---|
| **Latency** | Differential: p50 < 2 s, p95 < 5 s. Triage queue updates near-real-time. Safety screen synchronous within the Rx flow. |
| **Throughput** | Sized to peak concurrent consultations at the pilot site with ≥3× headroom; AI services horizontally scalable per load. |
| **Availability** | 99.9% during clinical hours; graceful degradation (rules + retrieval remain usable if the classifier is down). |
| **Scalability** | Stateless app tier autoscaling; vector index sharded; KB scalable from thousands to millions of episodes. |
| **Accessibility** | WCAG 2.1 AA: colour-plus-label status, high contrast, full keyboard navigation, sufficient touch targets. |
| **Localization** | Full Chinese/English bilingual UI; localizable terminology, formularies, and code systems. |
| **Auditability** | Every suggestion and decision logged immutably and traceable to a model version. |
| **Data residency** | Configurable to satisfy local jurisdiction and hospital policy; on-prem option available. |
| **Recoverability** | RPO ≤ 15 min, RTO ≤ 1 h for clinical services; backups and DR for the KB and audit log; tested restores. |
| **Maintainability** | Models, rules, and references updatable without re-engineering; one-click rollback. |
| **Compatibility** | Standards-based FHIR/HL7; supported on hospital-standard browsers/desktops. |

---

## 22. Deployment, Infrastructure & Operations

### 22.1 Environments

Separate **dev → staging → pre-prod (with de-identified data) → production** environments. Production-like staging is mandatory for clinical-impacting changes; no model reaches production without passing through shadow/canary (§14).

### 22.2 Deployment topology

- **Containerized services** orchestrated (Kubernetes or equivalent), one deployable unit per AI service and the app/API tier.
- **Deployment options:** managed cloud, hospital private cloud, or **on-prem/edge** for data-residency-sensitive sites.
- **Blue-green / canary releases** for the application tier; model promotion follows the §14 lifecycle independently of app releases.

### 22.3 CI/CD

- Automated build, test, security scan, and image signing on every change.
- Infrastructure as code; reproducible environments.
- Separate, gated pipeline for **model promotion** (offline gates → shadow → canary → full) distinct from application CD.

### 22.4 Configuration management

Site-specific configuration — code maps, formularies, triage weights, alert thresholds, residency, language — is externalized, versioned, and validated by conformance tests before activation. No site difference lives in code.

### 22.5 Graceful degradation tiers

Explicit, tested fallbacks so the clinician is never left with a blank screen and safety functions survive partial outages:

| Failure | Behaviour | What still works |
|---|---|---|
| Classifier offline | "Degraded mode" banner | Retrieval + rules still produce a differential |
| External drug reference offline | "Reduced coverage" banner | Local interaction set still screens; contraindication blocks hold |
| Triage scorer offline | Manual ordering with banner | Queue still visible; vitals still shown |
| HIS write-back failing | Sign-off queued, retried, surfaced | Clinician informed; nothing silently dropped |
| Vector index slow | Cascade to cached/precomputed results | UI stays responsive |

---

## 23. Observability, Reliability & Incident Response

### 23.1 Observability

- **Metrics:** latency (per service, p50/p95/p99), throughput, error rates, saturation; clinical KPIs (§26) as first-class metrics.
- **Logging:** structured, correlation-ID-traced across services; audit logging separate and immutable.
- **Tracing:** distributed traces for the consultation path to locate latency.
- **ML telemetry:** acceptance/override rates, calibration, drift, subgroup performance, alert dismiss rates.

### 23.2 Alerting & SLOs

SLOs defined for latency, availability, and write-back success; error-budget-based alerting; clinical-safety alerts (e.g. a spike in contraindication overrides, a drift threshold breach) routed to the Safety/ML on-call in addition to engineering.

### 23.3 Reliability

- Health checks and readiness probes per service; automatic restart and failover.
- Backups (KB, operational DB, audit log) with periodic **restore drills**; DR runbook meeting the §21 RPO/RTO.
- Capacity planning reviewed against real consultation volume.

### 23.4 Incident response

- Severity model with defined response times; on-call rotation spanning engineering and clinical safety.
- **Clinical-safety incident path** distinct from a technical outage: if an unsafe suggestion or a safety-rule failure is suspected, a documented escalation, containment (e.g. rollback / disable the affected capability), root-cause, and regulatory-reporting process applies.
- Blameless post-incident reviews feeding back into gates and monitors.

---

## 24. Quality Assurance & Test Strategy

| Layer | What is tested | How |
|---|---|---|
| **Unit** | Pure logic, scoring, mappers | Automated, high coverage on safety-critical code |
| **Rules/safety** | Every red-flag, interaction, dosing, do-not-miss rule | Golden test suite; 100% pass required to ship |
| **Model** | Accuracy, calibration, subgroup, long-tail | §14.4 offline gates + shadow |
| **Contract** | Internal API & FHIR boundary | Contract tests; adapter conformance per site |
| **Integration** | End-to-end HIS read/write, idempotency, reconciliation | Against HIS sandbox |
| **E2E / UX** | Each screen's full state set (§11) | Automated UI + manual clinical walkthroughs |
| **Performance** | Latency budgets, load, soak | Representative hardware & data volume |
| **Security** | SAST/DAST, dependency, pen-test | Pre-go-live and recurring |
| **Accessibility** | WCAG 2.1 AA | Automated + manual audit |
| **Localization** | Both languages, formularies, code maps | Per-locale test pass |
| **Clinical acceptance** | Real-world usefulness & safety | Physician-in-the-loop validation in pilot |

> **The safety golden suite is a hard gate.** No release ships if a single do-not-miss or contraindication test regresses.

---

## 25. Rollout Plan & Release Gates

A staged rollout that proves safety and value in one hospital before broadening — de-risking each step with evidence before the next. Phases map to the roadmap; each phase has explicit accuracy, safety, and adoption gates.

### Phase 1 · Foundation & pilot *(China hospital)*
Train on the 3,000+ Chinese episode seed set; integrate the partner hospital's HIS; deploy the diagnosis engine and drug-safety screen with a focused physician group. Stand up audit, observability, and security foundations.
**Goal / gate:** prove accuracy, safety, and clinician trust before workflow expansion.

### Phase 2 · Full clinical workflow
Add the triage board, outcome-feedback capture, and the continuous-learning loop. Ship the quick wins: active learning from overrides, UX click-reduction, data-quality pipeline, bias/fairness dashboards. Expand to more departments.
**Goal / gate:** measurable workflow and quality gains; fairness within thresholds.

### Phase 3 · Efficiency, intelligence & multi-site readiness
Model distillation + cascade, vector-index/caching optimization, MLOps with shadow/A-B, deeper HIS connectors; pilot the medical LLM + RAG layer (grounded, guarded) behind flags. Begin prospective clinical validation and regulatory documentation. Harden multi-tenant/multi-region/localization.
**Goal / gate:** faster, cheaper, smarter, shipping safely; model generalizes across sites.

### Phase 4 · Clinical breadth & network effects *(strategic)*
Multimodal inputs (imaging/labs/ECG), ambient voice scribe, predictive deterioration, specialty ensembles, on-prem inference, federated learning across sites, chronic-care/follow-up, wearables. Pursue regulatory clearance in the first market and a repeatable localization playbook.
**Goal / gate:** a compounding, defensible platform that gets smarter with every hospital it joins.

> **Earn trust before scale.** MediSense expands only when the evidence from the prior phase justifies it — protecting patients and the product's credibility alike. The regulatory and validation track starts in Phase 1, because it is the long pole that gates everything downstream.

---

## 26. Success Metrics, KPIs & SLAs

### 26.1 Product & clinical KPIs

| Category | KPI | Direction |
|---|---|---|
| **Accuracy** | Top-1 / Top-3 diagnostic accuracy | ↑ |
| **Accuracy** | Long-tail (rare-condition) accuracy | ↑ |
| **Calibration** | Calibration error / over-confidence rate | ↓ |
| **Safety** | Risky prescriptions caught before patient | ↑ |
| **Safety** | Subgroup accuracy gap (fairness) | ↓ |
| **Efficiency** | Latency (p95) per differential | ↓ |
| **Efficiency** | Compute cost per consultation | ↓ |
| **Efficiency** | Clicks / time per patient | ↓ |
| **Adoption** | Physician acceptance rate | ↑ |
| **Adoption** | Daily active clinicians | ↑ |
| **Operations** | Model deploy frequency / rollback rate | ↑ / ↓ |
| **Outcomes** | Recovery-feedback improvement on assisted cases | ↑ |

> **Discipline: no metric, no merge.** Every improvement names the KPI it moves and is validated in shadow/A-B before full rollout.

### 26.2 Operational SLAs / SLOs

| Indicator | Target |
|---|---|
| Availability (clinical hours) | 99.9% |
| Differential latency | p95 < 5 s |
| Write-back success (after sign-off, incl. retries) | ≥ 99.95%, zero silent loss |
| Critical escalation alert delivery | < 5 s, acknowledged & logged |
| RPO / RTO | ≤ 15 min / ≤ 1 h |
| Security vuln remediation (critical) | within defined SLA |

---

## 27. Risk Register & Mitigations

| Risk | Mitigation |
|---|---|
| Over-reliance / automation bias | Suggestion framing, mandatory confirmation, visible uncertainty, override logging keep the doctor engaged. |
| Data bias or skew | Subgroup monitoring; diverse, validated data; bias gates before release; runtime fairness alerts. |
| Incorrect suggestion reaching a decision | Hard safety rules, do-not-miss surfacing, calibrated confidence, human-in-the-loop at every commit. |
| Integration variability across hospitals | Adapter layer isolates site differences; standards-based FHIR/HL7; conformance tests per site. |
| Privacy & regulatory exposure | Encryption, minimization, residency controls, audit trails, CDS regulatory posture, DPIA. |
| Clinician adoption | Fits existing workflow, fast UX, transparent reasoning, phased rollout that earns trust early. |
| Alert fatigue | Severity model, low-value suppression, per-rule dismiss-rate monitoring and tuning. |
| Small / thin knowledge base (3,000 cases) | KB expansion, synthetic data for rare conditions (clinician-validated), retrieval+rules cold-start tolerance. |
| LLM hallucination (when RAG enabled) | Mandatory source citation; rules-layer veto; suppress uncited content; behind flags & gates. |
| Latency / cost creep from bigger models | Distillation, cascade, caching, monitored compute budgets. |
| Faster shipping (MLOps) regressions | Shadow testing, A/B, canary, automatic rollback, drift alerts, golden safety suite. |
| Multi-site data-residency exposure | Federated/local training, per-region residency, audit trails. |
| HIS write-back loss | Idempotent transactional write, retry, dead-letter, reconciliation job. |

> **The through-line.** Every risk is met by the same two commitments that define the product: **keep the physician in command**, and **always show the reasoning**. Those are not just principles — they are the safety mechanism.

---

## 28. Open Questions & Decision Log

Items to resolve with clinical, partner-hospital, and regulatory stakeholders before or during Phase 1. Tracked here so they are not lost.

| # | Open question | Owner | Status |
|---|---|---|---|
| 1 | Final NMPA device classification & required clinical-evidence depth for Phase 1 | Regulatory | Open |
| 2 | Authoritative drug-interaction reference source & update cadence for the China formulary | Clinical Pharmacy | Open |
| 3 | Partner HIS FHIR maturity vs. HL7 v2 fallback scope | Integration | Open |
| 4 | Triage scoring standard to anchor weights (NEWS2 vs. site-specific) | Clinical | Open |
| 5 | On-prem vs. private-cloud decision for the pilot (residency) | IT / Security | Open |
| 6 | Consent/governance basis for learning use of episodes | Privacy / Legal | Open |
| 7 | Definition & data source for structured "recovery outcome" scales | Clinical | Open |
| 8 | Secondary escalation channel for critical alerts (paging vs. messaging) | Clinical / IT | Open |

**Key decisions already made (recorded for traceability):** hybrid AI over single black box (§12); rules layer evaluated last with hard veto (§3); human-in-the-loop enforced server-side (§18.4); canonical model + adapter for integration (§9, §15); Markdown production spec as the source-of-truth format for this document; roadmap capabilities dark-shipped behind flags (§2.3, §12.5).

---

## 29. Glossary

- **Differential diagnosis** — an ordered list of candidate conditions that could explain a patient's symptoms, rather than a single answer.
- **Acuity score** — MediSense's computed measure of how critical and urgent a patient's condition is, used to order the triage queue.
- **Knowledge base** — the collection of outcome-labelled diagnostic episodes (symptoms → diagnosis → treatment → recovery) the system learns from.
- **Episode** — one complete past case in the knowledge base; the unit of learning.
- **Calibration** — alignment between stated confidence and real-world frequency, so a "70%" means roughly 70% in practice.
- **Retrieval (case-based)** — finding the most similar historical cases to reason from precedent and explain suggestions.
- **ANN** — approximate nearest-neighbour search, the technique that makes retrieval fast at scale.
- **OOD** — out-of-distribution; a patient unlike anything in the knowledge base, triggering low-confidence/escalation behaviour.
- **Clinical decision support (CDS)** — software that assists a clinician's judgement without replacing it; the regulatory posture of MediSense.
- **Do-not-miss** — a time-critical condition surfaced even at low probability because the cost of missing it is severe.
- **RAG** — retrieval-augmented generation; a roadmap reasoning layer that grounds any generated text in cited sources.
- **FHIR / HL7** — healthcare interoperability standards used to read from and write to hospital records.
- **HIS / EHR** — Hospital Information System / Electronic Health Record; the systems MediSense integrates with.
- **Human-in-the-loop** — the requirement that a clinician confirms every diagnosis and prescription before it takes effect.
- **Override** — when a doctor chooses differently from the AI suggestion; logged for audit and learning.
- **Shadow deployment** — running a new model against live traffic invisibly, with no patient impact, to validate it.
- **Canary release** — exposing a change to a small slice of traffic/users before full rollout.
- **RPO / RTO** — Recovery Point / Time Objective; the data-loss and downtime limits a disaster-recovery plan must meet.
- **MLOps** — the practice and tooling for training, evaluating, deploying, monitoring, and rolling back models reliably.
- **NMPA** — China's National Medical Products Administration, the first-market medical-device regulator.
- **PIPL** — China's Personal Information Protection Law, governing personal data in the first deployment market.

---

*This document describes intended production design and capability. All clinical examples are illustrative. MediSense is a decision-support tool intended to assist, not replace, licensed clinicians, and operates under the applicable medical-device and data-protection requirements of each market in which it is deployed. Scope and sequencing are subject to clinical validation, regulatory requirements, and partner priorities.*

*MediSense · AI Clinical Decision Support · Production Specification v2.0 · June 2026 · Confidential*
