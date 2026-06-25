"""Bilingual condition/drug terminology service (spec §6 `labels.py`).

Loads the site-configurable code map (SNOMED/ICD + EN/ZH labels). `lang` on a
request selects output language; ICD codes and confidence enums stay as-is.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@lru_cache
def _code_maps() -> dict:
    with open(DATA_DIR / "code_maps.json", encoding="utf-8") as f:
        return json.load(f)


def icd_for(condition: str) -> str | None:
    entry = _code_maps()["conditions"].get(condition)
    return entry.get("icd") if entry else None


def is_red_flag_condition(condition: str) -> bool:
    entry = _code_maps()["conditions"].get(condition)
    return bool(entry and entry.get("redFlag"))


def red_flag_conditions() -> set[str]:
    return {c for c, e in _code_maps()["conditions"].items() if e.get("redFlag")}


def condition_label(condition: str, lang: str) -> str:
    if lang != "zh":
        return condition
    entry = _code_maps()["conditions"].get(condition)
    return entry.get("zh", condition) if entry else condition


def drug_label(drug: str, lang: str) -> str:
    if lang != "zh":
        return drug
    return _code_maps()["drugs"].get(drug, drug)


def test_label(test: str, lang: str) -> str:
    if lang != "zh" or not test:
        return test
    return _code_maps().get("next_best_test_zh", {}).get(test, test)
