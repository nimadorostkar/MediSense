# MediSense — Product & Technical Documentation

**AI Clinical Decision Support Platform**

*Version 1.0 · June 2026 · Confidential — for clinical partners & investors*
*First deployment: Hospital pilot, China*

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [The Problem & Opportunity](#2-the-problem--opportunity)
3. [Product Vision & Principles](#3-product-vision--principles)
4. [Users & Personas](#4-users--personas)
5. [Capability Overview — The Four Pillars](#5-capability-overview--the-four-pillars)
6. [Diagnosis & Differential Probability Engine](#6-diagnosis--differential-probability-engine)
7. [Prescription & Drug-Interaction Safety](#7-prescription--drug-interaction-safety)
8. [Triage & Patient Prioritization](#8-triage--patient-prioritization)
9. [Hospital & EHR Integration](#9-hospital--ehr-integration)
10. [End-to-End User Flow](#10-end-to-end-user-flow)
11. [Screen-by-Screen UX Specification](#11-screen-by-screen-ux-specification)
12. [AI / ML Architecture](#12-ai--ml-architecture)
13. [Knowledge Base & Continuous Learning](#13-knowledge-base--continuous-learning)
14. [Data Model & System Architecture](#14-data-model--system-architecture)
15. [API Surface & Integration Contracts](#15-api-surface--integration-contracts)
16. [Security, Privacy & Compliance](#16-security-privacy--compliance)
17. [Design System](#17-design-system)
18. [Non-Functional Requirements](#18-non-functional-requirements)
19. [Roadmap & Rollout](#19-roadmap--rollout)
20. [Success Metrics & Risks](#20-success-metrics--risks)
21. [Glossary](#21-glossary)

---

## 1. Executive Summary

**MediSense** is an AI-powered clinical decision-support platform that sits beside the physician at the point of care. It learns from a curated knowledge base of real diagnostic episodes — patient symptoms, the doctor's diagnosis, the treatment and prescription that followed, and how well the patient recovered — and uses that knowledge to assist with the next patient.

When a new patient presents, MediSense reads their symptoms and history, compares them against thousands of similar past cases, and returns a ranked list of probable conditions with a confidence level and a transparent explanation of *why*. It then proposes evidence-aligned next steps: tests to confirm, and medications to consider — each one automatically screened against the patient's current drugs, allergies, and history so the doctor never has to chase a hidden interaction. Across a full ward or clinic, it continuously ranks patients by how urgent and critical their condition is, so the most fragile patient is never waiting at the back of the queue.

| Metric | Value |
|---|---|
| Seed diagnostic episodes in the initial knowledge base | **3,000+** |
| Core pillars | **Diagnose · Prescribe · Triage · Integrate** |
| Target time from symptom entry to ranked suggestions | **< 5 seconds** |
| Prescription suggestions screened for interactions & allergies | **100%** |

> **The core principle: assist, never replace.**
> MediSense never makes an autonomous medical decision. Every output is a **suggestion with its reasoning attached**, presented for the physician to accept, modify, or reject. The doctor's judgement is always the final authority — MediSense exists to make that judgement faster, safer, and better-informed.

**Who it serves and why it matters.** The first deployment is a hospital in China, where the system is trained and refined on Chinese clinical data and disease prevalence before expanding. For physicians, it reduces cognitive load and the risk of missed differentials. For hospitals, it standardizes quality, shortens decision time, and creates a learning asset that improves with every case. For patients, it means faster, safer, more consistent care.

---

## 2. The Problem & Opportunity

Medicine is judgement under pressure. A physician sees dozens of patients a day, each with incomplete information, overlapping symptoms, and a medication history that may hide a dangerous interaction. Knowledge is vast and growing; attention and time are not.

### The problems

- **Diagnostic uncertainty.** Many conditions share symptoms. Rare or atypical presentations are easy to miss, and a single anchoring assumption early in the consult can steer the whole diagnosis off course.
- **Information overload.** Guidelines, drug data, and prior records are scattered across systems. Synthesizing them for every patient, in minutes, is beyond what any individual can do reliably all day.
- **Medication risk.** Drug–drug and drug–allergy interactions are a leading cause of preventable harm. Catching them requires a full, current view of the patient's regimen — which is rarely at hand.
- **Triage under load.** In a busy ward, the sickest patient isn't always the loudest. Without a consistent way to rank acuity, urgent cases can wait while stable ones are seen.

### The opportunity

Every one of these problems is, at its heart, a pattern-matching and synthesis problem — exactly what modern AI does well, provided it is grounded in real, outcome-labelled clinical data. Hospitals already generate that data with every consultation; today it is filed and forgotten. MediSense turns the institution's own accumulated experience into a living assistant that gets sharper with every patient it sees.

> **The asset hiding in plain sight.** A hospital's archive of **symptoms → diagnosis → treatment → outcome** is the most valuable and underused dataset it owns. MediSense is the system that finally puts it to work for the next patient.

---

## 3. Product Vision & Principles

MediSense is an **intelligent clinical co-pilot**: a system trained on prior medical knowledge that observes a new patient's symptoms, proposes the most probable diagnoses, recommends safe treatment and prescriptions, and helps the doctor decide who to see first.

### What it IS

- A **decision-support** tool that augments the physician.
- A **transparent** reasoner that shows evidence behind every suggestion.
- A **safety net** that screens every prescription for interactions.
- A **learning system** that improves from real outcomes.
- A **connected** layer that reads the hospital's existing records.

### What it is NOT

- **Not** an autonomous doctor — it never decides alone.
- **Not** a replacement for examination, labs, or imaging.
- **Not** a black box — no suggestion arrives without a reason.
- **Not** a static model — it is refined continuously.
- **Not** a data silo — patient data stays governed and secure.

### Design principles

1. **Physician-in-command.** The interface always frames AI output as a suggestion to be confirmed. The doctor accepts, edits, or overrides with one tap, and every override teaches the system.
2. **Explainable by default.** Confidence scores and the specific symptoms, past cases, and rules driving each suggestion are always one tap away — never hidden.
3. **Safety over completeness.** When data is missing or signals conflict, MediSense says so and asks, rather than guessing. It flags uncertainty loudly.
4. **Fast at the point of care.** Sub-five-second suggestions, keyboard-light entry, and a layout designed for a clinician glancing between patient and screen.

---

## 4. Users & Personas

MediSense serves several roles inside the hospital. The product is designed primarily around the attending physician, with dedicated surfaces for nurses, pharmacists, and administrators.

### Dr. Li Wei — Attending Physician *(Primary)*

- **Goal:** diagnose accurately and quickly, prescribe safely, move to the next patient.
- **Frustrations:** fragmented records, fear of missing a rare condition, manual interaction checks.
- **MediSense gives:** ranked differentials with evidence, auto-screened prescriptions, full history in one view.

### Nurse Zhang — Triage & Ward Nurse *(Key)*

- **Goal:** capture vitals and symptoms accurately, surface the patients who can't wait.
- **Frustrations:** judging acuity under pressure, re-entering data.
- **MediSense gives:** a live, auto-ranked patient queue and structured intake.

### Pharmacist Chen — Clinical Pharmacist *(Key)*

- **Goal:** verify that every prescription is safe and appropriate before dispensing.
- **Frustrations:** incomplete medication lists, time-consuming manual checks.
- **MediSense gives:** a pre-screened Rx with interaction flags and rationale to verify.

### Director Wang — Medical Administrator *(Stakeholder)*

- **Goal:** raise care quality and consistency, manage risk, demonstrate outcomes.
- **Frustrations:** variable quality, limited visibility into diagnostic performance.
- **MediSense gives:** analytics on accuracy, override rates, and outcome trends.

---

## 5. Capability Overview — The Four Pillars

Everything MediSense does rests on four connected capabilities. Each is useful alone; together they form a continuous loop from a patient arriving to a safe, prioritized plan of care.

```
   ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
   │ DIAGNOSE │  →  │ PRESCRIBE│  →  │  TRIAGE  │  →  │ INTEGRATE│
   └──────────┘     └──────────┘     └──────────┘     └──────────┘
   Rank probable    Recommend &      Score acuity     Read records,
   conditions w/    auto-screen      & order the      write back the
   confidence       medication       patient queue    agreed plan
```

| Pillar | What it does | Primary user | Emphasis |
|---|---|---|---|
| **Diagnosis Engine** | Compares new symptoms to the case knowledge base and returns ranked differentials with probability and rationale. | Physician | Core |
| **Prescription & Safety** | Suggests treatment and drugs; checks every option against the patient's drugs, allergies, age, renal/hepatic status. | Physician, Pharmacist | Core |
| **Triage** | Continuously scores and ranks patients by criticality and urgency across the ward or clinic. | Nurse, Physician | Supporting |
| **Integration** | Connects to hospital systems (HIS/EHR) to pull history and write the confirmed diagnosis and Rx. | System / IT | Supporting |

> **Why the loop matters.** Diagnosis informs prescription; prescription depends on the integrated record; the record feeds triage; and the doctor's confirmed outcome flows back into the knowledge base — sharpening the next diagnosis. MediSense is a **closed learning loop**, not four separate tools.

---

## 6. Diagnosis & Differential Probability Engine

The heart of MediSense — turning a patient's symptoms into a ranked, explained set of probable diagnoses.

The physician describes or selects the patient's symptoms. The engine analyses them against the knowledge base of prior episodes and the patient's own record, then returns a **differential** — an ordered list of candidate conditions, each with a probability, a confidence band, and the evidence behind it.

### How a diagnosis is produced

1. **Symptom capture & normalization.** Free-text or structured symptom entry is mapped to a standard clinical vocabulary (e.g. SNOMED CT / ICD-aligned terms), with onset, duration, severity, and negatives ("no fever") captured explicitly.
2. **Patient-context enrichment.** Age, sex, vitals, chronic conditions, current medications, allergies, and recent labs are pulled from the integrated record to condition the analysis.
3. **Similarity & probabilistic matching.** A hybrid model retrieves the most similar past cases and combines them with a learned classifier and disease-prevalence priors to estimate the probability of each candidate condition.
4. **Ranking & calibration.** Candidates are ranked and their confidence calibrated, so a stated "78%" reflects real-world frequency. "Cannot-miss" critical conditions are surfaced even at lower probability.
5. **Explanation.** For each candidate the engine shows the supporting symptoms, contradicting signals, similar historical cases, and what additional test would most increase certainty.

### What the doctor sees

| Element | Description |
|---|---|
| **Ranked differential** | Each condition with a probability bar, confidence label (High / Moderate / Low), and a one-line "because…" summary. |
| **Evidence drawer** | Tap any condition to see matching symptoms, the count of similar past cases, typical outcomes, and contradicting findings. |
| **Next-best-test** | The single test or question that would most reduce uncertainty, so the doctor knows what to check next. |
| **Red-flag banner** | If symptoms match a time-critical condition (e.g. sepsis, MI, stroke), a prominent alert appears regardless of rank. |

> **Anti-anchoring by design.** The engine deliberately surfaces a **broad differential**, not a single answer, and always includes plausible "do-not-miss" alternatives. This counteracts the human tendency to lock onto the first plausible diagnosis.

### Example output *(illustrative)*

| Candidate condition | Probability | Confidence | Key supporting evidence |
|---|---|---|---|
| **Community-acquired pneumonia** | 78% | High | Fever, productive cough, focal crackles, raised CRP; 142 similar cases |
| Acute bronchitis | 41% | Moderate | Cough, low-grade fever; absence of focal signs lowers rank |
| Pulmonary embolism *(do-not-miss)* | 9% | Watch | Pleuritic pain + tachycardia; surfaced despite low probability |

*Illustrative example for documentation purposes only. Probabilities and confidence are produced per-patient and per-deployment from the trained model and are always presented for physician review.*

---

## 7. Prescription & Drug-Interaction Safety

From a confirmed diagnosis to a safe, personalized treatment and prescription — with every drug screened automatically.

Once the doctor confirms a diagnosis, MediSense proposes a treatment plan and candidate medications drawn from how similar cases were successfully treated. Critically, **every suggested drug is screened in real time** against the patient's full medication list, allergies, age, weight, and renal/hepatic function before it is ever shown.

### The safety screen — what every suggestion passes through

- **Drug–drug interactions.** Each candidate is checked against every medication the patient currently takes; contraindicated or risky combinations are blocked or flagged with severity.
- **Allergy & intolerance.** Documented allergies and prior adverse reactions are matched against the drug and its class, including cross-reactivity.
- **Dose for the patient.** Dosing is adjusted for age, weight, and renal/hepatic function; pediatric and geriatric limits are enforced.
- **Condition & context flags.** Pregnancy, comorbidities, and duplicate-therapy checks (two drugs of the same class) raise contextual warnings.

> **Nothing unsafe reaches the doctor unflagged.** A medication that fails a hard safety rule is never silently suggested. It is either withheld with an explanation or surfaced with a clear **severe interaction** banner and a safer alternative offered in its place.

### Interaction severity model

| Severity | Behaviour in the UI | Example |
|---|---|---|
| **Contraindicated** | Blocked; requires explicit override with reason; alternative offered. | Drug + drug with life-threatening combined effect |
| **Major** | Prominent warning; doctor must acknowledge before prescribing. | Significant additive risk needing monitoring |
| **Moderate** | Inline flag with guidance (e.g. adjust dose, monitor labs). | Manageable interaction with precautions |
| **Minor / info** | Subtle note, no interruption. | Low-significance or theoretical interaction |

### The prescription flow

```
Confirm Dx → Suggest plan → Auto-screen → Doctor decides → Sign & send
(accept a    (treatment &   (each option   (accept, swap,   (Rx written to
 diagnosis)   drug options)  vs. record)    or adjust;        record &
                                            override logged)  pharmacy)
```

---

## 8. Triage & Patient Prioritization

Across a busy ward or clinic, MediSense maintains a live, ordered queue of patients ranked by an **acuity score** that blends how critical and how urgent each patient's condition is — so the doctor always knows who needs attention first.

### What feeds the acuity score

- Vital signs and early-warning thresholds (e.g. respiratory rate, SpO₂, blood pressure, heart rate, temperature).
- Severity of the top candidate diagnoses and presence of any "do-not-miss" red flags.
- Trend — is the patient deteriorating or stable since the last reading?
- Time waiting, age, and known high-risk comorbidities.

### Priority bands

- **CRITICAL** — Immediate; possible life threat; pushed to top, alert raised.
- **URGENT** — See soon; significant risk or deteriorating trend.
- **ROUTINE** — Stable; standard queue order.

Bands are visually unmistakable (colour **and** label) and re-rank automatically as new vitals or results arrive.

> **Escalation, not just ordering.** When a patient crosses into **Critical**, MediSense does more than re-sort the list — it raises an active alert to the responsible clinician so a deteriorating patient is never missed because someone wasn't looking at the screen.

### The triage board *(illustrative)*

| # | Patient | Chief complaint | Key vitals | Top suggestion | Priority |
|---|---|---|---|---|---|
| 1 | Patient A, 67M | Chest pain, sweating | HR 118, BP 92/60 | ACS — do-not-miss | CRITICAL |
| 2 | Patient B, 24F | Severe abdominal pain | Temp 39.1°C | Appendicitis | URGENT |
| 3 | Patient C, 41M | Cough, mild fever | SpO₂ 97% | Bronchitis | ROUTINE |

*Illustrative example. Scores and bands are computed per-patient from live data and clinical rules and are always advisory to the care team.*

---

## 9. Hospital & EHR Integration

MediSense is only as good as the data it sees. It connects to the hospital's existing systems to pull a complete, current patient picture — and to write the confirmed diagnosis and prescription back where the rest of the care team can act on it.

### What it reads and writes

**Reads from the hospital record**

- Demographics, allergies, problem list, chronic conditions.
- Current and past medications (the basis of interaction checks).
- Recent vitals, lab results, and imaging reports.
- Encounter and visit history.

**Writes back (after doctor sign-off)**

- The confirmed diagnosis and coded problem.
- The signed prescription, routed to pharmacy.
- Ordered tests and follow-up plan.
- An audit trail of what was suggested vs. chosen.

### How it connects

- **Standards-based interfaces.** Primary integration via **HL7 FHIR** resources (`Patient`, `Condition`, `MedicationRequest`, `Observation`, `AllergyIntolerance`) with HL7 v2 messaging where the hospital's HIS requires it.
- **Adapter layer for legacy HIS.** A configurable adapter maps each hospital's local data formats and code systems to the MediSense canonical model, so onboarding a new site is configuration, not re-engineering.
- **China-first localization.** The first deployment integrates with the partner hospital's HIS and is tuned to local terminology, drug formularies, and coding conventions; the architecture keeps these as swappable configuration for future sites.
- **Security at the boundary.** All exchange is encrypted, authenticated, scoped to the minimum data needed, and fully logged. Data residency and governance follow the hospital's and jurisdiction's requirements.

> **Designed to fit in, not rip and replace.** MediSense layers on top of the systems a hospital already runs. The physician keeps their existing workflow; MediSense adds intelligence inside it rather than asking the institution to migrate.

---

## 10. End-to-End User Flow

A single consultation, walked through end to end — showing where MediSense assists and where the physician stays firmly in command.

1. **Patient arrives & is registered.** Nurse captures chief complaint and vitals at intake. MediSense immediately places the patient in the triage queue with a provisional priority band.
2. **Doctor opens the patient.** A unified patient view loads: integrated history, current medications, allergies, and recent results — no hunting across systems.
3. **Symptoms entered.** The doctor enters or refines symptoms. The engine returns a ranked differential within seconds, with red flags surfaced first.
4. **Doctor reviews the evidence.** They open the evidence drawer on the leading candidates, check supporting and contradicting signals, and see the suggested next-best test.
5. **Tests ordered (optional).** If confirmation is needed, tests are ordered through the integration; results flow back and update the differential automatically.
6. **Diagnosis confirmed.** The doctor accepts a diagnosis (or records their own). The choice — including any override of the AI's top suggestion — is logged for learning.
7. **Treatment & prescription.** MediSense proposes a plan and medications, each pre-screened for interactions, allergies, and dosing. The doctor adjusts and signs.
8. **Plan written back.** The signed diagnosis, prescription, and follow-up are written to the hospital record and routed to pharmacy and the care team.
9. **Outcome & feedback.** Recovery feedback and outcome are captured later and fed back into the knowledge base, improving suggestions for the next similar patient.

> **The human checkpoint is non-negotiable.** Steps 6 and 7 — confirming the diagnosis and signing the prescription — **always require explicit physician action**. MediSense can prepare everything, but the doctor commits it.

---

## 11. Screen-by-Screen UX Specification

Wireframe-level layouts of the four screens a physician lives in. The design language favours clarity, glanceability, and keeping AI output visibly framed as a suggestion.

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
- **Key interactions:** filter by department/priority/status; click a row to open the patient; critical rows pulse and trigger an active alert.
- **States:** empty (no patients), loading, live-updating as vitals arrive.

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
- **States:** awaiting symptoms, computing, results, results-updated-after-new-data.

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
- **States:** cleared, moderate-flag, major-flag (must acknowledge), contraindicated (blocked).

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
- **Key interactions:** view supporting/contradicting evidence; see similar historical cases and their outcomes; jump to the next-best test.

> **One consistent interaction model.** Across every screen, AI output uses the same visual grammar: a coloured confidence cue, a plain-language reason, and an always-available "show evidence." The doctor learns to trust it because it always shows its work.

---

## 12. AI / ML Architecture

MediSense uses a **hybrid architecture** — combining case-based retrieval, machine-learned classification, and an explicit clinical rules layer. No single technique is trusted alone; each covers the others' blind spots, and the rules layer guarantees safety.

### The three layers

1. **Retrieval (case-based).** Each past episode is embedded into a vector representation of its symptoms and context. A new patient retrieves the most similar historical cases — the engine reasons from real precedent, and can always point to "patients like this one."
2. **Learned classifier.** A supervised model trained on the labelled episodes estimates the probability of each condition from the symptom/context vector, capturing patterns beyond any single neighbour and calibrating the final probabilities.
3. **Clinical rules & safety.** An explicit, expert-curated rules layer enforces red-flag detection, interaction/allergy blocks, and dosing limits. Rules can hard-override the statistical layers — safety is never left to probability alone.

### The reasoning pipeline

```python
# Conceptual flow — symptoms in, explained suggestions out
patient   = enrich(symptoms, ehr_record)          # context: age, meds, labs, allergies
neighbors = retrieve(patient, knowledge_base)      # most similar past episodes
probs     = classify(patient, neighbors)           # calibrated disease probabilities
probs     = apply_rules(probs, patient)            # red flags + do-not-miss surfacing
dx        = rank_and_explain(probs, neighbors)     # ordered differential + evidence

rx = recommend_treatment(dx, knowledge_base)
rx = safety_screen(rx, patient.meds, patient.allergies)  # interactions, dose, allergy

return dx, rx   # presented to physician for confirmation
```

### Why hybrid, not a single black box

| Property | How the architecture delivers it |
|---|---|
| **Explainability** | Retrieval gives "cases like this"; rules give named reasons. Every suggestion traces to evidence. |
| **Safety** | The rules layer can override statistics — hard constraints (allergy, contraindication) always win. |
| **Cold-start tolerance** | For rare conditions with few examples, retrieval + rules still function where a pure classifier would be unreliable. |
| **Calibration** | Probabilities are calibrated against observed frequencies, so confidence is honest. |
| **Improvability** | New labelled episodes update retrieval and classifier without re-engineering the rules. |

> **Handling uncertainty honestly.** When evidence is thin or signals conflict, the engine widens its differential, lowers stated confidence, and explicitly asks for the missing information rather than projecting false certainty.

### Model lifecycle

- **Training data:** the curated knowledge base of labelled episodes (§13).
- **Evaluation:** held-out test set with Top-1 / Top-3 accuracy, calibration error, and subgroup performance gates before any release.
- **Versioning:** every model is versioned; every suggestion is traceable to the model version that produced it.
- **Rollout:** new models are shadow-tested against live traffic before they are allowed to influence the UI; regressions block promotion.

---

## 13. Knowledge Base & Continuous Learning

MediSense begins with a seed knowledge base of **3,000+ diagnostic episodes** and grows with every consultation. Each episode is a complete, outcome-labelled record — the unit the whole system learns from.

### Anatomy of a knowledge-base episode

1. **Symptoms & presentation.** Structured symptoms with onset, severity, and negatives, plus patient context at the time of the visit.
2. **Doctor's diagnosis.** The confirmed condition(s), coded to a standard vocabulary — the ground-truth label.
3. **Treatment & prescription.** The solution the doctor chose: procedures, medications, doses, and follow-up.
4. **Recovery feedback.** How well the patient improved — the outcome signal that tells the model which solutions actually worked.

> **Outcome is the secret ingredient.** Most systems learn "symptoms → diagnosis." MediSense also learns "treatment → **recovery**." Weighting suggestions by what genuinely led to good outcomes is what lets it recommend not just a plausible plan, but a plan that has *worked* for patients like this one.

### The continuous-learning loop

```
CAPTURE → CURATE → LEARN → EVALUATE → SERVE
new       validate,  update    measure     sharper
episode   de-id,     index &   accuracy &  suggestions
stored    code       model     calibration for next patient
```

### Quality & governance of the data

- **Human-validated labels:** diagnoses and outcomes come from physicians, not inferred guesses.
- **Bias monitoring:** performance is tracked across age, sex, and condition groups to catch skew before it harms care.
- **Versioned models:** every model release is versioned and evaluated against a held-out set; regressions block release.
- **De-identification:** data used for learning is governed and minimized per the security model in §16.

---

## 14. Data Model & System Architecture

A layered architecture keeps the clinical interface fast, the AI services independently scalable, and the integration with hospital systems cleanly separated behind an adapter.

### Logical architecture

```
┌──────────────────────────────────────────────────────────┐
│  PRESENTATION LAYER                                        │
│  Clinician web/desktop app — triage, patient view,        │
│  diagnosis & prescription surfaces                        │
├──────────────────────────────────────────────────────────┤
│  APPLICATION & API LAYER                                  │
│  Auth · session · request routing · write-back · audit    │
├──────────────────────────────────────────────────────────┤
│  AI SERVICES                                              │
│  Retrieval · Classification · Rules/Safety · Triage score │
├──────────────────────────────────────────────────────────┤
│  DATA & KNOWLEDGE LAYER                                   │
│  Episode KB · vector index · drug-interaction reference · │
│  canonical patient model                                  │
├──────────────────────────────────────────────────────────┤
│  INTEGRATION ADAPTER                                      │
│  FHIR / HL7 connectors → hospital HIS / EHR               │
└──────────────────────────────────────────────────────────┘
```

- **Presentation layer.** Clinician web/desktop app — triage board, patient view, diagnosis & prescription surfaces. Designed for speed and glanceability.
- **Application & API layer.** Orchestrates a consultation: auth, session, request routing to AI services, write-back, and audit logging.
- **AI services.** Independent services for retrieval, classification, rules/safety screening, and triage scoring — each separately deployable and scalable.
- **Data & knowledge layer.** The episode knowledge base, vector index, drug-interaction reference, and the canonical patient model.
- **Integration adapter.** FHIR/HL7 connectors mapping each hospital's HIS to the canonical model — the single place site-specific differences live.

### Core data entities

| Entity | Key attributes |
|---|---|
| **Patient** | ID, demographics, allergies, problem list, chronic conditions (from EHR via adapter) |
| **Encounter** | Visit context, presenting complaint, vitals, attending clinician, timestamp |
| **SymptomSet** | Coded symptoms with onset, severity, duration, and explicit negatives |
| **DiagnosisEpisode** | Symptoms · doctor's diagnosis · treatment/Rx · recovery outcome — the KB unit |
| **Medication** | Drug, class, dose, route; current & historical, for interaction screening |
| **Suggestion** | Ranked differential / Rx options with probability, confidence, evidence refs |
| **Decision** | What the doctor confirmed vs. what was suggested, with override reason & audit |
| **AcuityScore** | Computed priority band, contributing factors, timestamped trend |

> **The Decision entity is doubly valuable.** By recording suggestion *and* the doctor's final choice, MediSense builds both an **audit trail** for safety and governance and a **training signal** — every physician override is a lesson the system learns from.

---

## 15. API Surface & Integration Contracts

The application layer exposes a clean internal API consumed by the clinician app and a standards-based boundary to the hospital. The shapes below are illustrative and define intent, not a frozen contract.

### Internal clinical API (illustrative)

| Endpoint | Method | Purpose |
|---|---|---|
| `/encounters/{id}/symptoms` | `PUT` | Submit/refine the symptom set for an encounter |
| `/encounters/{id}/differential` | `GET` | Retrieve ranked differential with evidence |
| `/encounters/{id}/diagnosis` | `POST` | Physician confirms a diagnosis (logs decision) |
| `/encounters/{id}/prescription` | `POST` | Request screened treatment & drug suggestions |
| `/prescriptions/{id}/sign` | `POST` | Physician signs; triggers write-back to HIS |
| `/triage/queue` | `GET` | Live, acuity-ranked patient queue |
| `/episodes` | `POST` | Capture a completed episode for the knowledge base |

### Example: differential response *(illustrative)*

```json
{
  "encounterId": "enc_0098",
  "modelVersion": "dx-2026.06.1",
  "differential": [
    {
      "condition": "Community-acquired pneumonia",
      "icd": "J18.9",
      "probability": 0.78,
      "confidence": "high",
      "supporting": ["fever", "productive_cough", "focal_crackles", "raised_crp"],
      "contradicting": ["no_pleuritic_pain"],
      "similarCases": 142,
      "nextBestTest": "chest_xray"
    }
  ],
  "redFlags": [],
  "requiresPhysicianConfirmation": true
}
```

### Hospital boundary (FHIR resources)

| FHIR resource | Direction | Use |
|---|---|---|
| `Patient` | Read | Demographics, identifiers |
| `AllergyIntolerance` | Read | Allergy screening |
| `MedicationRequest` | Read / Write | Current meds in; signed Rx out |
| `Observation` | Read | Vitals & lab results |
| `Condition` | Write | Confirmed, coded diagnosis |
| `ServiceRequest` | Write | Ordered tests / follow-up |

---

## 16. Security, Privacy & Compliance

A clinical system handling patient data must earn trust before anything else. Security, privacy, and clinical safety are built into the architecture — not added afterward.

### Data protection

- Encryption in transit and at rest across all services.
- Role-based access control; clinicians see only what their role permits.
- Data minimization — only the fields needed for a task are exchanged.
- De-identification for data used in model learning.
- Configurable data residency to meet local jurisdiction rules.

### Accountability

- Full audit trail of every suggestion, view, and decision.
- Immutable logging of overrides and prescription sign-offs.
- Versioned models — every output is traceable to a model version.
- Clear attribution: actions are tied to an authenticated clinician.

### Clinical safety guardrails

- **Human-in-the-loop, always.** No diagnosis is recorded and no prescription is issued without explicit physician confirmation. The system cannot act autonomously on a patient.
- **Fail-safe defaults.** On low confidence, missing data, or conflicting signals, MediSense defers to the clinician and asks — it never fills gaps with confident guesses.
- **Hard safety rules win.** Allergy and contraindication blocks override any statistical suggestion; unsafe options are withheld or loudly flagged.
- **Continuous monitoring.** Accuracy, calibration, override rates, and subgroup performance are monitored so drift or bias is caught early.

> **Regulatory posture.** MediSense is positioned as **clinical decision support**, keeping the licensed physician as the decision-maker. Each deployment market — beginning with China — has its own medical-device and data-protection requirements; the product is built so that validation, documentation, and data-governance evidence can be produced for the relevant regulator of each market it enters.

---

## 17. Design System

A calm, clinical, high-contrast visual system built for fast reading at the point of care, where colour carries meaning — never decoration.

### Colour & meaning

| Token | Hex | Meaning |
|---|---|---|
| Teal · Primary | `#0F766E` | Brand, navigation, AI confidence-positive |
| Indigo · Action | `#4F46E5` | Prescription & interactive actions |
| Emerald · Safe | `#059669` | Cleared checks, routine priority, good outcomes |
| Amber · Caution | `#D97706` | Urgent priority, moderate warnings |
| Red · Critical | `#DC2626` | Red flags, contraindications, critical acuity |
| Ink · Text | `#0F172A` | Primary text and high-contrast labels |

### Typography

- A single, highly legible sans-serif family across the interface.
- Strict hierarchy: page title → section → card title → body → caption.
- Numbers (vitals, probabilities, doses) get tabular treatment for fast scanning.

### Principles in the interface

- **Glanceability.** Priority and confidence are readable in under a second from across a room. Status is shown by colour **and** label, never colour alone — accessible to colour-vision deficiency.
- **Suggestion framing.** AI output always carries a confidence cue, a plain-language reason, and an "accept / edit / reject" control — visually distinct from confirmed clinician input.
- **Progressive disclosure.** The summary is always visible; the evidence and detail are one tap away. The doctor controls depth.
- **Low-friction entry.** Keyboard-light, autocomplete-driven symptom and drug entry, optimized for speed during a live consult.

*Bilingual interface (Chinese / English) is a first-class requirement for the China deployment; all components are built for localization from day one.*

---

## 18. Non-Functional Requirements

| Area | Target / Requirement |
|---|---|
| **Latency** | < 5 s from symptom entry to ranked differential; triage queue updates in near-real-time |
| **Availability** | High-availability deployment; AI services degrade gracefully (rules + retrieval remain usable if the classifier is down) |
| **Scalability** | AI services independently horizontally scalable per load |
| **Accessibility** | Colour-plus-label status; high contrast; keyboard navigation |
| **Localization** | Full Chinese/English bilingual UI; localizable terminology, formularies, and code systems |
| **Auditability** | Every suggestion and decision logged immutably and traceable to a model version |
| **Data residency** | Configurable to satisfy local jurisdiction and hospital policy |
| **Recoverability** | Backups and disaster recovery for the knowledge base and audit log |

---

## 19. Roadmap & Rollout

A staged rollout that proves safety and value in one hospital before broadening — de-risking each step with evidence before the next.

### Phase 1 · Foundation & pilot *(China hospital)*
Train on the 3,000+ Chinese episode seed set; integrate with the partner hospital's HIS; deploy the diagnosis engine and drug-safety screen with a focused group of physicians.
**Goal:** prove accuracy, safety, and clinician trust.

### Phase 2 · Full clinical workflow
Add the triage board, outcome-feedback capture, and the continuous-learning loop. Expand to more departments in the pilot hospital.
**Goal:** demonstrate measurable workflow and quality gains.

### Phase 3 · Multi-site & specialty depth
Onboard additional hospitals via the integration adapter; deepen specialty coverage; mature analytics for administrators.
**Goal:** prove the model generalizes across sites.

### Phase 4 · Scale & new markets
Expand beyond the initial region with localization of formularies, language, and regulatory evidence per market.
**Goal:** a repeatable deployment playbook.

> **Earn trust before scale.** Each phase has explicit accuracy, safety, and adoption gates. MediSense expands only when the evidence from the prior phase justifies it — protecting patients and the product's credibility alike.

---

## 20. Success Metrics & Risks

### Success metrics

| Metric | What it tells us |
|---|---|
| **Top-1 / Top-3 diagnostic accuracy** | How often the confirmed diagnosis appears as the engine's leading / top-three suggestion. |
| **Calibration error** | Whether stated confidence matches real-world frequency — honesty of the probabilities. |
| **Interaction catches** | Count of risky prescriptions flagged before they reached the patient. |
| **Time-to-decision** | Reduction in time from patient open to confirmed plan. |
| **Physician acceptance rate** | How often suggestions are accepted — a proxy for usefulness and trust. |
| **Outcome improvement** | Recovery-feedback trends for cases where MediSense assisted. |

### Key risks & mitigations

| Risk | Mitigation |
|---|---|
| Over-reliance / automation bias | Suggestion framing, mandatory confirmation, visible uncertainty, and override logging keep the doctor engaged. |
| Data bias or skew | Subgroup performance monitoring; diverse, validated training data; bias gates before model release. |
| Incorrect suggestion reaching a decision | Hard safety rules, do-not-miss surfacing, calibrated confidence, and human-in-the-loop at every commit. |
| Integration variability across hospitals | Adapter layer isolates site differences; standards-based FHIR/HL7 reduce bespoke work. |
| Privacy & regulatory exposure | Encryption, minimization, residency controls, audit trails, and a decision-support regulatory posture. |
| Clinician adoption | Fits existing workflow, fast UX, transparent reasoning, and phased rollout that earns trust early. |

> **The through-line.** Every risk is met by the same two commitments that define the product: **keep the physician in command**, and **always show the reasoning**. Those are not just principles — they are the safety mechanism.

---

## 21. Glossary

- **Differential diagnosis** — an ordered list of candidate conditions that could explain a patient's symptoms, rather than a single answer.
- **Acuity score** — MediSense's computed measure of how critical and urgent a patient's condition is, used to order the triage queue.
- **Knowledge base** — the collection of outcome-labelled diagnostic episodes (symptoms → diagnosis → treatment → recovery) the system learns from.
- **Episode** — one complete past case in the knowledge base; the unit of learning.
- **Calibration** — alignment between stated confidence and real-world frequency, so a "70%" means roughly 70% in practice.
- **Retrieval (case-based)** — finding the most similar historical cases to reason from precedent and explain suggestions.
- **Clinical decision support (CDS)** — software that assists a clinician's judgement without replacing it; the regulatory posture of MediSense.
- **Do-not-miss** — a time-critical condition surfaced even at low probability because the cost of missing it is severe.
- **FHIR / HL7** — healthcare interoperability standards used to read from and write to hospital records.
- **HIS / EHR** — Hospital Information System / Electronic Health Record; the systems MediSense integrates with.
- **Human-in-the-loop** — the requirement that a clinician confirms every diagnosis and prescription before it takes effect.
- **Override** — when a doctor chooses differently from the AI suggestion; logged for audit and learning.

---

*This document describes intended product design and capability. All clinical examples are illustrative. MediSense is a decision-support tool intended to assist, not replace, licensed clinicians, and operates under the applicable medical-device and data-protection requirements of each market in which it is deployed.*

*MediSense · AI Clinical Decision Support · Product & Technical Documentation v1.0 · June 2026 · Confidential*
