"""Treatment recommender (spec §7.3, §12.4).

Given a (confirmed or top) diagnosis, assemble an outcome-weighted treatment
plan from the knowledge base and run every medication through the drug-safety
screen. If a contraindication is found, the offending drug is flagged and the
plan is annotated — the safety layer wins (spec §12.6).
"""
from __future__ import annotations

from . import drug_safety
from .labels import localize
from .reasoning import treatment_rationale


def build_treatment(
    condition: str,
    icd: str,
    treatment_dict: dict,
    outcomes: dict,
    allergies: list[str],
    current_meds: list[str],
    lang: str = "en",
) -> dict:
    meds = list(treatment_dict.get("medications", []))
    plan = list(treatment_dict.get("plan", []))
    monitoring = treatment_dict.get("monitoring", "")

    flags = drug_safety.screen(meds, allergies, current_meds)

    # Hard block: mark contraindicated meds in their note so the UI can show it.
    blocked = {
        f["message"].split(" conflicts")[0].lower()
        for f in flags if f["severity"] == "Contraindicated"
    }
    for m in meds:
        if any(b in (m.get("drug", "").lower()) for b in blocked):
            m["note"] = ((m.get("note", "") + " ⚠ BLOCKED: allergy conflict — substitute.").strip())

    return {
        "bestDiagnosis": localize(condition, lang),
        "icd": icd,
        "rationale": treatment_rationale(condition, outcomes, lang),
        "plan": plan,
        "medications": meds,
        "safety": flags,
        "monitoring": monitoring,
        "requiresPhysicianConfirmation": True,
    }
