"""Triage acuity scorer (spec §8).

A transparent, rule-weighted composite (NEWS2-style vitals + red-flag presence +
risk factors) — not a black box. Each factor and its weight is returned so the
score is explainable on demand. Weights are site-configurable in production.
"""

from __future__ import annotations

from app.engine.embeddings import _tokenize
from app.engine.rules import RED_FLAG_RULES, _rule_matches

CRITICAL = "CRITICAL"
URGENT = "URGENT"
ROUTINE = "ROUTINE"


def _vitals_factors(vitals: dict) -> dict[str, int]:
    f: dict[str, int] = {}
    if (v := vitals.get("spo2")) is not None:
        if v < 90:
            f["spo2_critical"] = 3
        elif v < 94:
            f["spo2_low"] = 2
    if (v := vitals.get("hr")) is not None:
        if v > 130:
            f["hr_critical"] = 3
        elif v > 110:
            f["hr_high"] = 2
    if (v := vitals.get("rr")) is not None:
        if v > 24:
            f["rr_critical"] = 3
        elif v > 20:
            f["rr_high"] = 1
    if (v := vitals.get("bp_sys")) is not None:
        if v < 90:
            f["bp_critical"] = 3
        elif v < 100:
            f["bp_low"] = 1
    if (v := vitals.get("temp")) is not None:
        if v >= 39.5 or v < 35:
            f["temp_extreme"] = 2
        elif v >= 38:
            f["fever"] = 1
    return f


def compute_acuity(patient: dict) -> dict:
    vitals = patient.get("vitals", {}) or {}
    tokens = set(_tokenize(patient.get("text", "")))
    sex = patient.get("sex")
    age = patient.get("age")

    factors = _vitals_factors(vitals)

    red_flag = any(_rule_matches(r, tokens, vitals, sex) for r in RED_FLAG_RULES)
    if red_flag:
        factors["red_flag"] = 4
    if age is not None and age >= 70:
        factors["age_70_plus"] = 1

    score = sum(factors.values())
    has_critical_vital = any(
        k in factors for k in ("spo2_critical", "hr_critical", "rr_critical", "bp_critical")
    )

    if score >= 6 or has_critical_vital or (red_flag and score >= 4):
        band = CRITICAL
    elif score >= 3 or red_flag:
        band = URGENT
    else:
        band = ROUTINE

    return {"band": band, "score": score, "factors": factors, "trend": "stable", "redFlag": red_flag}
