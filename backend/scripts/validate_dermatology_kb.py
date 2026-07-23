"""Validate the normalized dermatology KB without third-party dependencies."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "data" / "dermatology"

EXPECTED_MODULES = {
    "disease.json", "symptoms.json", "physical_exam.json",
    "diagnostic_criteria.json", "differential_diagnosis.json",
    "laboratory_tests.json", "imaging.json", "treatment.json",
    "drug_database.json", "patient_education.json",
    "clinical_guidelines.json", "ai_rules.json",
}
ALLOWED_CONTENT_STATUSES = {"catalog_only", "legacy_curated", "clinically_validated"}
ALLOWED_REVIEW_STATUSES = {
    "not_reviewed", "migration_pending_revalidation", "approved", "retired"
}


class ValidationError(ValueError):
    """Raised when a knowledge-base invariant fails."""


def load(name: str, kb_dir: Path = KB_DIR) -> dict[str, Any]:
    with (kb_dir / name).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
        raise ValidationError(f"{name}: expected an object with a records array")
    if payload.get("metadata", {}).get("record_count") != len(payload["records"]):
        raise ValidationError(f"{name}: metadata record_count does not match records")
    return payload


def _require_unique(records: list[dict[str, Any]], field: str, name: str) -> set[str]:
    values: list[str] = []
    for record in records:
        value = record.get(field)
        if not isinstance(value, str) or not value:
            raise ValidationError(f"{name}: every record requires a non-empty {field}")
        values.append(value)
    if len(values) != len(set(values)):
        raise ValidationError(f"{name}: duplicate {field}")
    return set(values)


def validate(kb_dir: Path = KB_DIR) -> dict[str, int]:
    manifest_path = kb_dir / "manifest.json"
    if not manifest_path.exists():
        raise ValidationError("manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    declared = set(manifest.get("modules", []))
    if declared != EXPECTED_MODULES:
        raise ValidationError(
            f"manifest modules differ: missing={EXPECTED_MODULES - declared}, "
            f"extra={declared - EXPECTED_MODULES}"
        )

    payloads = {name: load(name, kb_dir) for name in sorted(EXPECTED_MODULES)}
    diseases = payloads["disease.json"]["records"]
    if len(diseases) != 300 or manifest.get("disease_count") != 300:
        raise ValidationError("the MVP catalog must contain exactly 300 diseases")

    disease_ids = _require_unique(diseases, "id", "disease.json")
    _require_unique(diseases, "slug", "disease.json")
    for disease in diseases:
        if disease.get("content_status") not in ALLOWED_CONTENT_STATUSES:
            raise ValidationError(f"{disease['id']}: invalid content_status")
        review = disease.get("clinical_review", {})
        if review.get("status") not in ALLOWED_REVIEW_STATUSES:
            raise ValidationError(f"{disease['id']}: invalid clinical review status")
        if (
            disease["content_status"] == "clinically_validated"
            and (review.get("status") != "approved" or not review.get("reviewer"))
        ):
            raise ValidationError(
                f"{disease['id']}: validated content requires an approving reviewer"
            )

    actual_counts = Counter(disease["category"] for disease in diseases)
    if dict(actual_counts) != manifest.get("category_counts"):
        raise ValidationError("manifest category_counts do not match disease.json")

    drug_records = payloads["drug_database.json"]["records"]
    drug_ids = _require_unique(drug_records, "id", "drug_database.json")
    _require_unique(drug_records, "slug", "drug_database.json")

    module_count = 0
    actionable_disease_ids: set[str] = set()
    for filename, payload in payloads.items():
        if filename in {"disease.json", "drug_database.json"}:
            continue
        records = payload["records"]
        _require_unique(records, "id", filename)
        for record in records:
            disease_id = record.get("disease_id")
            if disease_id not in disease_ids:
                raise ValidationError(f"{filename}/{record['id']}: unknown disease_id")
            module_count += 1
            if filename in {"treatment.json", "ai_rules.json"}:
                actionable_disease_ids.add(disease_id)

    by_id = {disease["id"]: disease for disease in diseases}
    catalog_only = {
        disease_id for disease_id, disease in by_id.items()
        if disease["content_status"] == "catalog_only"
    }
    unsafe = catalog_only & actionable_disease_ids
    if unsafe:
        raise ValidationError(
            f"catalog-only diseases have actionable records: {sorted(unsafe)}"
        )

    for treatment in payloads["treatment.json"]["records"]:
        if treatment.get("requires_physician_confirmation") is not True:
            raise ValidationError(f"{treatment['id']}: physician confirmation is required")
        for tier in treatment.get("tiers", []):
            for item in tier.get("items", []):
                ref = item.get("drug_id")
                if ref is not None and ref not in drug_ids:
                    raise ValidationError(f"{treatment['id']}: unknown drug_id {ref}")

    for rule in payloads["ai_rules.json"]["records"]:
        disease = by_id[rule["disease_id"]]
        if disease["clinical_review"]["status"] != "approved" and rule.get("enabled") is not False:
            raise ValidationError(f"{rule['id']}: unapproved clinical rule must be disabled")

    return {
        "diseases": len(diseases),
        "categories": len(actual_counts),
        "drugs": len(drug_records),
        "module_records": module_count,
    }


if __name__ == "__main__":
    result = validate()
    print(
        "Dermatology KB valid: "
        f"{result['diseases']} diseases, {result['categories']} categories, "
        f"{result['drugs']} drugs, {result['module_records']} clinical module records"
    )
