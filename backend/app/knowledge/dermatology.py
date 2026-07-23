"""Indexed read-only access to the normalized dermatology knowledge base."""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_KB_DIR = Path(__file__).resolve().parents[2] / "data" / "dermatology"
CLINICAL_MODULES = (
    "symptoms",
    "physical_exam",
    "diagnostic_criteria",
    "differential_diagnosis",
    "laboratory_tests",
    "imaging",
    "treatment",
    "patient_education",
    "clinical_guidelines",
    "ai_rules",
)


class DermatologyKnowledgeBase:
    """Load once, then serve O(1) disease and module lookups.

    Returned objects are deep copies so callers cannot mutate the process-wide
    cached clinical knowledge.
    """

    def __init__(self, kb_dir: Path = DEFAULT_KB_DIR) -> None:
        self.kb_dir = kb_dir
        self.manifest = self._read_object("manifest.json")
        diseases = self._read_records("disease.json")
        drugs = self._read_records("drug_database.json")

        self._diseases_by_id = {record["id"]: record for record in diseases}
        self._diseases_by_slug = {record["slug"]: record for record in diseases}
        self._drugs_by_id = {record["id"]: record for record in drugs}
        self._modules: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for module in CLINICAL_MODULES:
            by_disease: dict[str, list[dict[str, Any]]] = {}
            for record in self._read_records(f"{module}.json"):
                by_disease.setdefault(record["disease_id"], []).append(record)
            self._modules[module] = by_disease

    def _read_object(self, filename: str) -> dict[str, Any]:
        with (self.kb_dir / filename).open(encoding="utf-8") as handle:
            return json.load(handle)

    def _read_records(self, filename: str) -> list[dict[str, Any]]:
        return self._read_object(filename)["records"]

    @property
    def disease_count(self) -> int:
        return len(self._diseases_by_id)

    def get_disease(
        self, identifier: str, *, include_modules: bool = True
    ) -> dict[str, Any] | None:
        """Get one disease by immutable ID or canonical slug."""
        disease = self._diseases_by_id.get(identifier) or self._diseases_by_slug.get(identifier)
        if disease is None:
            return None
        result = copy.deepcopy(disease)
        if not include_modules:
            return result
        disease_id = disease["id"]
        result["modules"] = {
            module: copy.deepcopy(by_disease.get(disease_id, []))
            for module, by_disease in self._modules.items()
        }
        self._resolve_treatment_drugs(result["modules"]["treatment"])
        return result

    def search_catalog(
        self, query: str = "", *, category: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Search canonical names, slugs, and aliases without clinical inference."""
        if limit < 1:
            return []
        terms = [term for term in re.split(r"\W+", query.casefold()) if term]
        matches: list[tuple[int, str, dict[str, Any]]] = []
        for disease in self._diseases_by_id.values():
            if category is not None and disease["category"] != category:
                continue
            haystack = " ".join(
                [disease["name"], disease["slug"], *disease.get("aliases", [])]
            ).casefold()
            if terms and not all(term in haystack for term in terms):
                continue
            score = sum(haystack.startswith(term) for term in terms)
            matches.append((-score, disease["name"], disease))
        matches.sort(key=lambda item: (item[0], item[1]))
        return [copy.deepcopy(item[2]) for item in matches[:limit]]

    def _resolve_treatment_drugs(self, treatments: list[dict[str, Any]]) -> None:
        for treatment in treatments:
            for tier in treatment.get("tiers", []):
                for item in tier.get("items", []):
                    drug_id = item.get("drug_id")
                    if drug_id:
                        item["drug"] = copy.deepcopy(self._drugs_by_id[drug_id])


@lru_cache(maxsize=1)
def dermatology_kb() -> DermatologyKnowledgeBase:
    """Return the immutable process-wide dermatology repository."""
    return DermatologyKnowledgeBase()
