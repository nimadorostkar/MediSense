"""Real-time drug-safety screen (spec §6 `drug_safety.py`, §7).

Allergy (incl. class cross-reactivity), drug–drug interaction, and dosing-bound
checks against a versioned reference. Severity graded
Contraindicated > Major > Moderate > Minor; `Contraindicated` is a hard block —
the drug is withheld and a safer alternative offered. Nothing unsafe reaches the
doctor unflagged (spec §1.3, §7.1).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.observability.metrics import SAFETY_BLOCKS

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
SEVERITY_RANK = {"Contraindicated": 3, "Major": 2, "Moderate": 1, "Minor": 0}
# Boolean drug attributes that behave like interaction classes.
_ATTR_CLASSES = {"qt_prolonging"}


@lru_cache
def _ref() -> dict:
    with open(DATA_DIR / "drug_reference.json", encoding="utf-8") as f:
        return json.load(f)


def _norm(name: str) -> str:
    return (name or "").strip().lower()


def _drug_entry(name: str) -> dict:
    return _ref()["drugs"].get(_norm(name), {})


def _classes(name: str) -> set[str]:
    e = _drug_entry(name)
    classes = set(e.get("classes", []))
    classes.add(_norm(name))
    for attr in _ATTR_CLASSES:
        if e.get(attr):
            classes.add(attr)
    return classes


@dataclass
class Flag:
    severity: str
    message: str


@dataclass
class ScreenResult:
    medications: list[dict]
    flags: list[Flag] = field(default_factory=list)
    has_hard_block: bool = False
    drugref_version: str = settings.drugref_version
    reduced_coverage: bool = False  # external reference offline (spec §7.5)

    def sorted_flags(self) -> list[Flag]:
        return sorted(self.flags, key=lambda f: SEVERITY_RANK.get(f.severity, 0), reverse=True)


def _parse_mg(dose: str | None) -> float | None:
    if not dose:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*mg", dose.lower())
    return float(m.group(1)) if m else None


def _allergy_flags(drug: str, allergies: list[str]) -> list[Flag]:
    flags: list[Flag] = []
    classes = _classes(drug)
    xref = _ref()["allergy_cross_reactivity"]
    for raw in allergies:
        a = _norm(raw)
        # Direct allergen == drug name or one of its classes → hard block.
        if a in classes:
            flags.append(
                Flag("Contraindicated", f"{drug} conflicts with documented {raw} allergy.")
            )
            continue
        # Mapped cross-reactivity (e.g. penicillin → cephalosporin caution).
        for entry in xref.get(a, []):
            if entry["target_class"] in classes:
                note = entry.get("note", "")
                msg = (
                    f"{drug} ({entry['target_class']}) vs documented {raw} allergy"
                    + (f" — {note}." if note else ".")
                )
                flags.append(Flag(entry["severity"], msg))
    return flags


def _alternative_for(drug: str, allergies: list[str]) -> str | None:
    classes = _classes(drug)
    alts_map = _ref()["alternatives"]
    for cls in classes:
        for alt in alts_map.get(cls, []):
            # Don't offer an alternative the patient is also allergic to.
            if not _allergy_flags(alt, allergies):
                return alt.capitalize()
    return None


def _interaction_flags(agents_a: set[str], agents_b: set[str], label_a: str, label_b: str) -> list[Flag]:
    flags: list[Flag] = []
    for rule in _ref()["interactions"]:
        a, b = rule["a"], rule["b"]
        hit = (a in agents_a and b in agents_b) or (b in agents_a and a in agents_b)
        if hit:
            flags.append(Flag(rule["severity"], f"{label_a} + {label_b}: {rule['message']}"))
    return flags


def _dosing_flags(drug: str, dose: str | None, age: int | None, vitals: dict) -> list[Flag]:
    flags: list[Flag] = []
    e = _drug_entry(drug)
    bounds = _ref()["dosing_bounds"].get(_norm(drug), {})
    egfr = vitals.get("egfr")

    if age is not None:
        if e.get("pediatric_contra") and age < e.get("pediatric_min_age", 16):
            flags.append(
                Flag("Contraindicated", f"{drug} is contraindicated under "
                     f"{e.get('pediatric_min_age', 16)} ({bounds.get('pediatric_note', 'paediatric risk')}).")
            )
        elif e.get("pediatric_min_age") and age < e["pediatric_min_age"]:
            flags.append(
                Flag("Major", f"{drug} not recommended under {e['pediatric_min_age']} years.")
            )
        if age >= 65 and bounds.get("geriatric_note"):
            flags.append(Flag("Moderate", f"{drug} — geriatric caution: {bounds['geriatric_note']}."))

    if egfr is not None:
        rc = e.get("renal_contra_egfr")
        if rc and egfr < rc:
            flags.append(
                Flag("Contraindicated", f"{drug} contraindicated when eGFR < {rc} (eGFR {egfr}).")
            )
        elif e.get("renal_adjust") and egfr < 30:
            flags.append(Flag("Moderate", f"{drug} — reduce dose in renal impairment (eGFR {egfr})."))

    mg = _parse_mg(dose)
    max_single = bounds.get("adult_max_single_mg")
    if mg and max_single and mg > max_single:
        flags.append(
            Flag("Major", f"{drug} dose {mg:g} mg exceeds the usual max single dose ({max_single} mg).")
        )
    return flags


def screen(
    medications: list[dict],
    patient: dict,
    *,
    reference_online: bool = True,
) -> ScreenResult:
    """Screen candidate medications. `reference_online=False` simulates the
    external-reference outage: local set still screens and contraindication
    blocks still hold (spec §7.5 degraded mode)."""
    allergies = [a for a in patient.get("allergies", []) if a]
    current_meds = [m for m in patient.get("medications", []) if m]
    age = patient.get("age")
    vitals = patient.get("vitals", {}) or {}

    current_agents = set()
    for m in current_meds:
        current_agents |= _classes(m)

    final_meds: list[dict] = []
    flags: list[Flag] = []
    has_hard_block = False
    offered: set[str] = set()

    for med in medications:
        drug = med.get("drug", "")
        med = dict(med)
        med_flags: list[Flag] = []

        med_flags += _allergy_flags(drug, allergies)
        med_flags += _interaction_flags(_classes(drug), current_agents, drug, "current medication")
        # Candidate-vs-candidate (duplicate therapy etc.)
        for other in medications:
            if other is med or other.get("drug") == drug:
                continue
            med_flags += _interaction_flags(_classes(drug), _classes(other.get("drug", "")), drug, other.get("drug", ""))
        med_flags += _dosing_flags(drug, med.get("dose"), age, vitals)

        hard = any(f.severity == "Contraindicated" for f in med_flags)
        if hard:
            has_hard_block = True
            SAFETY_BLOCKS.labels(category="contraindication").inc()
            alt = _alternative_for(drug, allergies)
            if alt and alt not in offered:
                offered.add(alt)
                # Withhold the unsafe drug; offer a screened safer alternative.
                block_msg = next(f.message for f in med_flags if f.severity == "Contraindicated")
                flags.append(
                    Flag("Contraindicated", f"{block_msg} Blocked — safer alternative offered: {alt}.")
                )
                final_meds.append({
                    "drug": alt, "dose": "", "route": med.get("route", ""),
                    "frequency": "", "duration": "",
                    "note": f"Safer alternative to {drug} (screened clear).",
                })
            else:
                flags.append(
                    Flag("Contraindicated", next(f.message for f in med_flags
                         if f.severity == "Contraindicated") + " Blocked — choose an alternative.")
                )
            # Do NOT add the contraindicated drug to the final plan.
            continue

        # Non-hard flags: keep the drug but surface every flag.
        flags.extend(med_flags)
        if med_flags:
            worst = max(med_flags, key=lambda f: SEVERITY_RANK.get(f.severity, 0))
            med["note"] = (med.get("note") or "") or f"{worst.severity}: see safety screen."
        final_meds.append(med)

    # De-duplicate identical flags, keep highest severity ordering.
    seen = set()
    deduped: list[Flag] = []
    for f in sorted(flags, key=lambda f: SEVERITY_RANK.get(f.severity, 0), reverse=True):
        key = (f.severity, f.message)
        if key not in seen:
            seen.add(key)
            deduped.append(f)

    return ScreenResult(
        medications=final_meds,
        flags=deduped,
        has_hard_block=has_hard_block,
        reduced_coverage=not reference_online,
    )
