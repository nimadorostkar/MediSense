"""Drug-safety screen (spec §7).

Every proposed medication passes through allergy, drug–drug interaction, and
dosing checks against a versioned reference. Four-level severity model
(Contraindicated > Major > Moderate > Minor). A Contraindicated hit is a hard
block — the rules layer's veto applied to prescribing.
"""
from __future__ import annotations

import json
from pathlib import Path

_REF_PATH = Path(__file__).resolve().parent.parent / "data" / "drug_reference.json"
_REF = json.loads(_REF_PATH.read_text(encoding="utf-8")) if _REF_PATH.exists() else {}

_INTERACTIONS = _REF.get("interactions", [])
_ALLERGY_CLASSES = _REF.get("allergy_classes", {})
_DOSING = _REF.get("dosing", {})


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _allergy_conflicts(drug: str, allergies: list[str]) -> str | None:
    d = _norm(drug)
    for allergy in allergies:
        a = _norm(allergy)
        if not a:
            continue
        members = _ALLERGY_CLASSES.get(a, [a])
        if any(m in d or d in m for m in members):
            return allergy
    return None


def screen(
    proposed: list[dict], allergies: list[str], current_meds: list[str]
) -> list[dict]:
    """Return a list of {severity, message} flags for the proposed meds."""
    flags: list[dict] = []
    proposed_names = [_norm(m.get("drug", "")) for m in proposed]
    all_meds = proposed_names + [_norm(m) for m in current_meds]

    # 1. Allergy screen — contraindicated, hard block.
    for m in proposed:
        conflict = _allergy_conflicts(m.get("drug", ""), allergies)
        if conflict:
            flags.append({
                "severity": "Contraindicated",
                "message": f"{m.get('drug')} conflicts with documented {conflict} allergy — do not prescribe; choose an alternative class.",
            })

    # 2. Drug–drug interactions (proposed × proposed and proposed × current).
    seen: set[tuple[str, str]] = set()
    for inter in _INTERACTIONS:
        a, b = _norm(inter["a"]), _norm(inter["b"])
        if any(a in m or m in a for m in all_meds) and any(b in m or m in b for m in all_meds):
            key = tuple(sorted((a, b)))
            if key in seen:
                continue
            seen.add(key)
            flags.append({
                "severity": inter.get("severity", "Moderate"),
                "message": inter.get("message", f"Interaction between {a} and {b}."),
            })

    # 3. Dosing guidance (Minor advisory).
    for m in proposed:
        info = _DOSING.get(_norm(m.get("drug", "")))
        if info and not m.get("dose"):
            flags.append({
                "severity": "Minor",
                "message": f"Suggested dosing for {m.get('drug')}: {info.get('adult', 'see formulary')}. {info.get('note', '')}".strip(),
            })

    order = {"Contraindicated": 0, "Major": 1, "Moderate": 2, "Minor": 3}
    flags.sort(key=lambda f: order.get(f["severity"], 9))
    return flags


def has_hard_block(flags: list[dict]) -> bool:
    return any(f["severity"] == "Contraindicated" for f in flags)


def drugref_version() -> str:
    from ..versions import DRUGREF_VERSION
    return DRUGREF_VERSION
