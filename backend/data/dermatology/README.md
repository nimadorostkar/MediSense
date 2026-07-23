# MediSense Dermatology Knowledge Base

This directory is the normalized dermatology MVP data contract. It contains
exactly 300 canonical disease records across 14 categories. Clinical content is
stored separately and joined by the immutable `disease_id`.

## Collections

| File | Purpose |
|---|---|
| `disease.json` | Canonical identity, category, aliases, ICD-10, and review state |
| `symptoms.json` | Presenting symptoms and severity vocabulary |
| `physical_exam.json` | Morphology, distribution, and examination findings |
| `diagnostic_criteria.json` | Criteria and named scoring systems |
| `differential_diagnosis.json` | Ranked candidates and differentiating features |
| `laboratory_tests.json` | Diagnostic, baseline, and pre-treatment tests |
| `imaging.json` | Imaging indications and studies |
| `treatment.json` | Tiered therapies and follow-up; always physician-confirmed |
| `drug_database.json` | Deduplicated drug identities referenced by treatments |
| `patient_education.json` | Patient-facing counseling points |
| `clinical_guidelines.json` | Guideline citations and lifecycle status |
| `ai_rules.json` | Versioned executable reasoning rules |

Every JSON collection has `metadata` and `records`. Module records use
`disease_id` as a foreign key. Treatment items reference `drug_database.json`
with `drug_id`.

## Clinical lifecycle

- `catalog_only`: identity and taxonomy only; it must have no treatment or AI
  rule. Most of the 300-condition catalog intentionally starts here.
- `legacy_curated`: migrated verbatim from the existing 25-condition core data;
  it is usable by the legacy demo but requires revalidation before the new
  normalized records become executable.
- `clinically_validated`: requires an approving reviewer and review timestamp.

All migrated AI rules are disabled. Guideline records are
`citation_required`. This prevents taxonomy completeness from being mistaken
for clinical completeness.

## Build and validate

From `backend/`:

```bash
python scripts/build_dermatology_kb.py
python scripts/validate_dermatology_kb.py
pytest -q tests/test_dermatology_kb.py
```

The builder is deterministic and only derives clinical details from
`dermatology_core_data_EN.json`; it never creates recommendations for the new
catalog-only conditions.

## Production governance

Before changing a disease to `clinically_validated`, require:

1. named dermatologist/pharmacist review as appropriate;
2. directly cited, jurisdiction-specific guideline and formulary versions;
3. effective and review-expiry dates;
4. contraindication, interaction, pregnancy, pediatric, renal, and hepatic
   safety review;
5. regression cases and dual review for every enabled AI rule.

This dataset is clinical decision-support content, not an autonomous diagnosis
or prescribing authority.
