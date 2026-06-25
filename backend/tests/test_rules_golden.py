"""Rules / drug-safety GOLDEN SUITE — 100% pass is a hard release gate (spec §11,
§24). Every red-flag, allergy, interaction, dosing, and do-not-miss case.

These exercise the engine directly so they are fast and deterministic.
"""

from __future__ import annotations

import pytest

from app.engine.classify import Candidate
from app.engine.drug_safety import SEVERITY_RANK, screen
from app.engine.rules import apply_rules


def _patient(text="", **kw):
    base = {
        "text": text,
        "vitals": {},
        "allergies": [],
        "medications": [],
        "negatives": [],
        "age": None,
        "sex": None,
        "lang": "en",
    }
    base.update(kw)
    return base


def _cand(name, prob=0.1, icd=""):
    return Candidate(condition=name, icd=icd, probability=prob, raw_share=prob, similar_cases=1)


# ── Red-flag / do-not-miss surfacing (even at low probability) ────────────────
@pytest.mark.parametrize(
    "text,vitals,sex,expected",
    [
        ("67M chest pain radiating to left arm, diaphoretic", {}, "M", "Acute coronary syndrome"),
        (
            "70M sudden left-sided weakness, facial droop, slurred speech",
            {},
            "M",
            "Acute ischaemic stroke",
        ),
        ("55M fever, rigors, confusion", {"bp_sys": 85, "hr": 124}, "M", "Sepsis"),
        ("71M sudden tearing chest pain radiating to back", {}, "M", "Aortic dissection"),
        (
            "28F pleuritic chest pain, breathless, recent long flight, calf swelling",
            {},
            "F",
            "Pulmonary embolism",
        ),
    ],
)
def test_red_flag_surfaced_even_when_absent_from_stats(text, vitals, sex, expected):
    # Statistics return an unrelated low-risk condition; the rule must still
    # surface and pin the do-not-miss condition with a banner.
    candidates = [_cand("Acute bronchitis", 0.5)]
    result = apply_rules(candidates, _patient(text, vitals=vitals, sex=sex))
    assert result.has_red_flag
    assert result.banner
    surfaced = {c.condition: c for c in result.candidates}
    assert expected in surfaced
    assert surfaced[expected].pinned_watch is True


def test_appendicitis_does_not_false_fire_on_chest_pain():
    # Precision: right-sided *chest* pain + fever must NOT trip appendicitis.
    result = apply_rules(
        [_cand("Community-acquired pneumonia", 0.4)],
        _patient("62F fever, right pleuritic chest pain, productive cough", sex="F"),
    )
    assert "Acute appendicitis" not in {c.condition for c in result.candidates}


def test_critical_vitals_raise_banner():
    result = apply_rules([_cand("Acute bronchitis", 0.6)], _patient("cough", vitals={"spo2": 88}))
    assert any("vitals" in f.lower() or "spo2" in f.lower() for f in result.red_flags)


# ── Allergy screen ───────────────────────────────────────────────────────────
def test_penicillin_allergy_blocks_amoxicillin_offers_azithromycin():
    res = screen([{"drug": "Amoxicillin", "dose": "500 mg"}], _patient(allergies=["penicillin"]))
    assert res.has_hard_block
    assert any(f.severity == "Contraindicated" for f in res.flags)
    final = {m["drug"] for m in res.medications}
    assert "Amoxicillin" not in final  # withheld
    assert "Azithromycin" in final  # safer alternative offered


def test_penicillin_cephalosporin_cross_reactivity_major():
    res = screen([{"drug": "Ceftriaxone", "dose": "1 g"}], _patient(allergies=["penicillin"]))
    assert any(f.severity == "Major" for f in res.flags)


# ── Interaction severities ───────────────────────────────────────────────────
def test_warfarin_nsaid_major():
    res = screen([{"drug": "Ibuprofen", "dose": "400 mg"}], _patient(medications=["warfarin"]))
    assert any(f.severity == "Major" for f in res.flags)


def test_warfarin_macrolide_major():
    res = screen([{"drug": "Azithromycin", "dose": "500 mg"}], _patient(medications=["warfarin"]))
    assert any(f.severity == "Major" for f in res.flags)


def test_warfarin_aspirin_anticoagulant_antiplatelet_major():
    res = screen([{"drug": "Aspirin", "dose": "75 mg"}], _patient(medications=["warfarin"], age=50))
    assert any(f.severity == "Major" for f in res.flags)


# ── Dosing bounds (pediatric / geriatric / renal) ────────────────────────────
def test_pediatric_aspirin_contraindicated():
    res = screen([{"drug": "Aspirin", "dose": "300 mg"}], _patient(age=8))
    assert res.has_hard_block
    assert any(f.severity == "Contraindicated" for f in res.flags)


def test_geriatric_paracetamol_caution():
    res = screen([{"drug": "Paracetamol", "dose": "1 g"}], _patient(age=82))
    assert any(f.severity in ("Moderate", "Minor") for f in res.flags)


def test_renal_nitrofurantoin_contraindicated_low_egfr():
    res = screen([{"drug": "Nitrofurantoin", "dose": "100 mg"}], _patient(vitals={"egfr": 30}))
    assert res.has_hard_block


def test_clear_screen_when_no_conflicts():
    res = screen([{"drug": "Salbutamol", "dose": "5 mg"}], _patient())
    assert not res.has_hard_block
    assert all(f.severity != "Contraindicated" for f in res.flags)


def test_severity_ordering_constant():
    assert (
        SEVERITY_RANK["Contraindicated"]
        > SEVERITY_RANK["Major"]
        > SEVERITY_RANK["Moderate"]
        > SEVERITY_RANK["Minor"]
    )
