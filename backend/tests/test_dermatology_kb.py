"""Integrity and safety tests for the normalized dermatology knowledge base."""

from __future__ import annotations

import json
from pathlib import Path

from app.knowledge.dermatology import DermatologyKnowledgeBase
from scripts.validate_dermatology_kb import EXPECTED_MODULES, validate

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "dermatology"


def _records(name: str) -> list[dict]:
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))["records"]


def test_normalized_kb_integrity():
    result = validate(DATA_DIR)
    assert result["diseases"] == 300
    assert result["categories"] == 14


def test_all_requested_modules_are_present():
    assert {path.name for path in DATA_DIR.glob("*.json")} - {"manifest.json"} == EXPECTED_MODULES


def test_high_priority_mvp_conditions_are_in_catalog():
    slugs = {record["slug"] for record in _records("disease.json")}
    required = {
        "vitiligo", "melasma", "atopic_dermatitis", "plaque_psoriasis",
        "pemphigus_vulgaris", "bullous_pemphigoid", "impetigo", "cellulitis",
        "herpes_zoster", "tinea_corporis", "scabies", "acne_vulgaris",
        "hidradenitis_suppurativa", "alopecia_areata", "onychomycosis",
        "seborrheic_keratosis", "basal_cell_carcinoma", "melanoma",
        "cutaneous_small_vessel_vasculitis", "dermatomyositis",
        "stevens_johnson_syndrome", "toxic_epidermal_necrolysis",
        "diaper_dermatitis", "infantile_hemangioma",
    }
    assert required <= slugs


def test_catalog_only_conditions_have_no_actionable_content():
    diseases = {record["id"]: record for record in _records("disease.json")}
    actionable = {
        record["disease_id"]
        for name in ("treatment.json", "ai_rules.json")
        for record in _records(name)
    }
    assert all(
        diseases[disease_id]["content_status"] != "catalog_only"
        for disease_id in actionable
    )


def test_unreviewed_ai_rules_are_disabled():
    assert all(record["enabled"] is False for record in _records("ai_rules.json"))


def test_repository_joins_modules_and_resolves_drugs():
    kb = DermatologyKnowledgeBase(DATA_DIR)
    psoriasis = kb.get_disease("plaque_psoriasis")
    assert kb.disease_count == 300
    assert psoriasis is not None
    assert psoriasis["id"] == "DER-051"
    treatment = psoriasis["modules"]["treatment"][0]
    drug_items = [
        item
        for tier in treatment["tiers"]
        for item in tier["items"]
        if "drug_id" in item
    ]
    assert drug_items
    assert drug_items[0]["drug"]["name"]


def test_repository_catalog_search_is_not_clinical_inference():
    kb = DermatologyKnowledgeBase(DATA_DIR)
    matches = kb.search_catalog("melanoma", category="skin_cancer")
    assert {record["slug"] for record in matches} >= {
        "melanoma", "acral_lentiginous_melanoma", "nodular_melanoma"
    }
