"""Tests for the file-grounded follow-up answerer (engine/kb_answer.py).

Every answer must be templated from the uploaded data files
(`dermatology_core_data_{EN,CN}.json`, `drug_reference.json`); a question the
files cannot answer returns None (the endpoint then says exactly that). No AI
model is ever involved in producing these answers.
"""

from __future__ import annotations

from app.engine import kb_answer

_PSORIASIS_REPLY = {
    "differential": [
        {"condition": "Psoriasis", "because": "matches: silvery white scales"}
    ]
}


def test_drug_dose_comes_from_files():
    out = kb_answer.answer("what dose of methotrexate should I use?", _PSORIASIS_REPLY, "en")
    assert out is not None
    assert "WEEKLY" in out  # dose string copied verbatim from the KB file
    assert "uploaded" in out  # source footer names the files


def test_drug_pregnancy_contraindication_from_files():
    out = kb_answer.answer("is tazarotene safe in pregnancy?", _PSORIASIS_REPLY, "en")
    assert out is not None
    # The contra list copied verbatim from the KB entry — not a fallback line.
    assert "Contraindicated in: pregnancy" in out


def test_condition_safety_resolves_via_last_reply():
    out = kb_answer.answer("is that safe in pregnancy?", _PSORIASIS_REPLY, "en")
    assert out is not None
    # Real extracted file content (Tazarotene contra / Acitretin special), not
    # the "files do not record pregnancy-specific guidance" fallback sentence.
    assert "do not record" not in out
    assert "contraindicated in pregnancy" in out.lower() or "Contraception 2 years" in out


def test_differential_uses_kb_differentiators():
    out = kb_answer.answer(
        "why psoriasis instead of seborrheic dermatitis?", _PSORIASIS_REPLY, "en"
    )
    assert out is not None
    assert "greasy yellow scales" in out  # differentiator text from the KB file


def test_tests_facet_lists_kb_labs():
    out = kb_answer.answer("which tests should I order?", _PSORIASIS_REPLY, "en")
    assert out is not None
    assert "CBC" in out


def test_unknown_drug_returns_none():
    # Lisinopril is in no uploaded file → refuse rather than answer from AI memory.
    assert kb_answer.answer("what is the dose of lisinopril?", None, "en") is None


def test_off_topic_returns_none():
    assert kb_answer.answer("who won the football world cup?", None, "en") is None


def test_drug_reference_file_is_used():
    out = kb_answer.answer("any warfarin interactions to know?", None, "en")
    assert out is not None
    assert "INR" in out or "anticoagulant" in out.lower()


def test_zh_treatment_from_files():
    reply = {"differential": [{"condition": "银屑病", "because": ""}]}
    out = kb_answer.answer("银屑病的治疗方案是什么？", reply, "zh")
    assert out is not None
    assert "银屑病" in out
    assert "资料文件" in out  # zh source footer
