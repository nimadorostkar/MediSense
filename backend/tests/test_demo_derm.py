"""Golden tests for the offline dermatology demo diagnoser (engine/demo_derm.py).

These lock in ranking quality so regressions are caught: each classic
presentation must rank the right condition first; the malignancy/emergency
banner must fire only for genuine do-not-miss cases; non-dermatological input
must fall through (return None); vague input must ask rather than guess.
"""

from __future__ import annotations

import pytest

from app.engine import demo_derm

# (presentation, expected top slug fragment, expect red-flag banner)
GOLDEN = [
    ("well demarcated erythematous plaques with silvery white scales on extensor "
     "elbows knees and scalp", "Psoriasis", False),
    ("chronic itchy eczematous patches in the flexural creases of a child, "
     "recurrent, dry skin", "Atopic Dermatitis", False),
    ("annular scaly pruritic patch with central clearing and active raised border "
     "on the trunk", "Tinea", False),
    ("honey colored crusts and superficial erosions on the face of a child, "
     "contagious", "Impetigo", False),
    ("comedones inflammatory papules and pustules with seborrhea on the face of a "
     "teenager", "Acne", False),
    ("painful clustered vesicles on an erythematous base recurring at the same "
     "site on the lip", "Herpes", False),
    ("well demarcated erythema and vesicles after contact with a nickel watch "
     "strap", "Contact Dermatitis", False),
    ("central facial persistent erythema with telangiectasia and flushing, no "
     "comedones", "Rosacea", False),
    ("follicular papules and pustules centered on hair follicles on the thighs",
     "Folliculitis", False),
    # Do-not-miss — banner must fire:
    ("changing mole with asymmetry irregular border multiple colors and diameter "
     "over 8mm", "Melanoma", True),
    ("slowly growing pearly papule with telangiectasia and rolled border and "
     "central ulcer on the nose", "Basal Cell Carcinoma", True),
    ("rapidly growing indurated hyperkeratotic ulcerated nodule on sun damaged "
     "lip of an elderly man", "Squamous Cell Carcinoma", True),
    ("painful oral erosions and flaccid blisters with positive nikolsky sign",
     "Pemphigus", True),
]


@pytest.mark.parametrize("text,expected_top,expect_rf", GOLDEN)
def test_demo_ranks_correct_condition_first(text, expected_top, expect_rf):
    reply = demo_derm.diagnose(text, "en")
    assert reply is not None, f"expected a dermatological answer for: {text}"
    top = reply["differential"][0]
    assert expected_top.lower() in top["condition"].lower(), (
        f"top was {top['condition']!r}, expected {expected_top!r}"
    )
    assert 0 < top["probability"] <= 95
    assert top["confidence"] in {"High", "Moderate", "Low", "Watch"}
    assert bool(reply["redFlag"]) is expect_rf, (
        f"banner mismatch for {expected_top}: redFlag={reply['redFlag']!r}"
    )


@pytest.mark.parametrize(
    "text",
    [
        "67M crushing chest pain radiating to jaw, sweating, diabetic",
        "severe headache with photophobia, neck stiffness and fever",
        "dysuria, urinary frequency and suprapubic discomfort",
        "pain",
    ],
)
def test_non_dermatological_falls_through(text):
    # None → the general retrieval/classifier engine handles it.
    assert demo_derm.diagnose(text, "en") is None


def test_confident_case_includes_treatment_and_workup():
    reply = demo_derm.diagnose(
        "well demarcated erythematous plaques with silvery scales on the elbows and scalp", "en"
    )
    assert reply["treatment"] is not None
    tx = reply["treatment"]
    assert tx["medications"], "expected first-line medications from the KB"
    assert reply["nextBestTest"]
    assert reply["requiresPhysicianConfirmation"] is True


def test_vague_input_asks_rather_than_guesses():
    reply = demo_derm.diagnose("itchy red rash on the arm", "en")
    assert reply is not None
    # Too little signal → no differential, no treatment, no cancer named.
    assert reply["differential"] == []
    assert reply["treatment"] is None
    assert reply["ood"] is True


def test_bilingual_chinese_presentation():
    reply = demo_derm.diagnose("伸侧红斑斑块覆银白色鳞屑，边界清楚", "zh")
    assert reply is not None
    assert "银屑病" in reply["differential"][0]["condition"]
    assert reply["treatment"]["medications"][0]["drug"]  # Chinese drug name present


def test_severity_selects_stronger_tier():
    mild = demo_derm.diagnose(
        "a few comedones and papules on the face", "en"
    )
    severe = demo_derm.diagnose(
        "severe nodulocystic acne with confluent nodules and scarring on the face", "en"
    )
    # Severe picks a systemic/isotretinoin tier — different meds than the mild topical tier.
    mild_drugs = {m["drug"] for m in (mild["treatment"] or {}).get("medications", [])}
    severe_drugs = {m["drug"] for m in (severe["treatment"] or {}).get("medications", [])}
    assert severe_drugs and severe_drugs != mild_drugs
