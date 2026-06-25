"""Rules / safety layer (spec §12.4, §12.6).

Deterministic, versioned, and evaluated LAST so it can hard-override the
statistical layers. It does two jobs here:
  1. Raise red-flag banners for time-critical presentations.
  2. Pin "do-not-miss" conditions into the differential as 'Watch' even when the
     classifier ranks them low — the anti-anchoring guarantee (README key feature).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .embeddings import normalize


@dataclass
class RuleHit:
    red_flag: str | None = None
    do_not_miss: list[dict] = field(default_factory=list)  # [{condition, icd, because}]


# Each rule: any of `triggers` tokens present → fire. `all_of` requires every group.
_RULES = [
    {
        "name": "acs",
        "all_of": [["chest", "pain"], ["arm", "diaphoretic", "sweaty", "jaw", "radiating"]],
        "red_flag": "Possible acute coronary syndrome — obtain a 12-lead ECG and troponin now; do not wait for the full differential.",
        "do_not_miss": {"condition": "Acute coronary syndrome", "icd": "I24.9",
                        "because": "chest pain with radiation / diaphoresis is a do-not-miss"},
    },
    {
        "name": "stroke",
        "all_of": [["face", "arm", "speech", "weakness", "droop", "slurred", "numbness"], ["sudden"]],
        "red_flag": "Possible acute stroke — activate stroke pathway and obtain emergent non-contrast CT; note last-known-well time.",
        "do_not_miss": {"condition": "Acute ischemic stroke", "icd": "I63.9",
                        "because": "sudden focal neurological deficit is a do-not-miss"},
    },
    {
        "name": "pe",
        "all_of": [["dyspnea", "breath", "chest"], ["leg", "calf", "immobile", "tachycardia", "hemoptysis"]],
        "red_flag": "Consider pulmonary embolism — assess Wells score and consider CT pulmonary angiogram.",
        "do_not_miss": {"condition": "Pulmonary embolism", "icd": "I26.99",
                        "because": "dyspnea with thrombosis risk factors is a do-not-miss"},
    },
    {
        "name": "sepsis",
        "all_of": [["fever", "hypotension", "confusion"], ["tachycardia", "hypotension", "confusion", "rigors"]],
        "red_flag": "Screen for sepsis — check lactate, blood cultures and start the sepsis bundle if criteria met.",
        "do_not_miss": {"condition": "Sepsis", "icd": "A41.9",
                        "because": "infection with hemodynamic / mental-status change is a do-not-miss"},
    },
    {
        "name": "meningitis",
        "all_of": [["headache", "fever"], ["neck", "stiff", "photophobia", "rash"]],
        "red_flag": "Consider meningitis — do not delay empiric antibiotics for imaging if strongly suspected.",
        "do_not_miss": {"condition": "Bacterial meningitis", "icd": "G00.9",
                        "because": "fever with meningism is a do-not-miss"},
    },
]


def evaluate(symptom_text: str) -> RuleHit:
    toks = set(normalize(symptom_text))
    hit = RuleHit()
    flags: list[str] = []
    for rule in _RULES:
        if all(any(tok in toks for tok in group) for group in rule["all_of"]):
            flags.append(rule["red_flag"])
            hit.do_not_miss.append(rule["do_not_miss"])
    if flags:
        hit.red_flag = " ".join(flags)
    return hit
