"""Regression tests for the file-grounding guarantee.

Every clinical statement shown in the chat must come from the uploaded data
files. These tests pin the leaks found by the adversarial review:

1. A Chinese clinical question that merely CONTAINS a greeting (你好，会传染吗？)
   is NOT small talk — the AI is never called for it.
2. An English diagnosis-challenging turn built from filler words
   ("ok doc, you sure?") is NOT small talk — the grounded card stands.
3. No configuration (LLM_REASONING / ZHIPU_API_KEY) can reintroduce
   model-generated clinical summaries or disable the file-based derm KB.
4. The small-talk AI reply is screened after generation: a hallucinated
   drug/dose is rejected and the deterministic canned line stands.
Plus correctness fixes to the file answerer itself (警示 alerts, drug-reference
matching, colloquial name resolution, prescriptive card retention).
"""

from __future__ import annotations

import json

import pytest

from app.config import settings
from app.engine import conversation, demo_derm, kb_answer
from app.routers.clinical import _GREETING, _NOT_IN_FILES, _is_smalltalk

_PSORIASIS_CASE = (
    "well demarcated erythematous plaques with silvery scales on the extensor "
    "elbows and scalp"
)


class _FakeProvider:
    name = "fake"

    def __init__(self, text: str = "FAKE-AI-TEXT"):
        self.text = text
        self.calls: list[tuple] = []

    async def reason(self, system: str, user: str, *, max_tokens: int) -> str:
        self.calls.append(("reason", system, user))
        return self.text

    async def chat(self, messages, *, system, max_tokens=480, temperature=0.6) -> str:
        self.calls.append(("chat", system, messages))
        return self.text


@pytest.fixture
def ai_on(monkeypatch):
    """Conversational AI layer ON with a fake provider (no network)."""
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "conversational_ai", True)
    monkeypatch.setattr(settings, "llm_provider", "auto")
    fake = _FakeProvider()
    monkeypatch.setattr(conversation, "get_chat_provider", lambda: fake)
    return fake


# ── 1+2: smalltalk classification is strict ──────────────────────────────────


def test_smalltalk_rejects_questions_and_mixed_turns():
    # Pure social turns qualify.
    assert _is_smalltalk("thank you")
    assert _is_smalltalk("Thanks so much, doc!")
    assert _is_smalltalk("good morning")
    assert _is_smalltalk("你好")
    assert _is_smalltalk("谢谢！")
    assert _is_smalltalk("好的，谢谢")
    # Questions and clinical residue never qualify.
    assert not _is_smalltalk("ok doc, you sure?")
    assert not _is_smalltalk("you sure?")
    assert not _is_smalltalk("it good yes?")
    assert not _is_smalltalk("你好，会传染吗？")
    assert not _is_smalltalk("好的，会复发吗？")
    assert not _is_smalltalk("谢谢，接下来怎么办？")
    assert not _is_smalltalk("你好，孕妇能用吗?")
    assert not _is_smalltalk("thanks — what dose?")


@pytest.mark.asyncio
async def test_zh_greeting_plus_clinical_question_never_reaches_ai(client, ai_on):
    r = await client.post(
        "/api/clinical",
        json={"messages": [{"role": "doctor", "text": "你好，会传染吗？"}], "lang": "zh"},
    )
    reply = json.loads(r.json()["text"])
    assert ai_on.calls == []  # the AI was never consulted
    assert reply["summary"] != ai_on.text
    assert reply["summary"] == _NOT_IN_FILES["zh"]


@pytest.mark.asyncio
async def test_en_challenge_turn_keeps_grounded_card(client, ai_on):
    r = await client.post(
        "/api/clinical",
        json={
            "messages": [
                {"role": "doctor", "text": _PSORIASIS_CASE},
                {"role": "ai", "text": "Leading consideration: Psoriasis."},
                {"role": "doctor", "text": "ok doc, you sure?"},
            ],
            "lang": "en",
        },
    )
    reply = json.loads(r.json()["text"])
    assert ai_on.calls == []
    # The file-grounded diagnosis card stands (not replaced by AI or a bubble).
    assert reply["differential"]
    assert "psoriasis" in reply["differential"][0]["condition"].lower()


@pytest.mark.asyncio
async def test_smalltalk_with_ai_off_returns_canned_greeting(client):
    r = await client.post(
        "/api/clinical",
        json={
            "messages": [
                {"role": "doctor", "text": _PSORIASIS_CASE},
                {"role": "ai", "text": "Leading consideration: Psoriasis."},
                {"role": "doctor", "text": "thank you"},
            ],
            "lang": "en",
        },
    )
    reply = json.loads(r.json()["text"])
    assert reply["summary"] == _GREETING["en"]
    assert reply["aiChat"] is True


# ── 3: no config can reintroduce model-generated clinical text ───────────────


def test_llm_reasoning_config_cannot_enable_model_answers(monkeypatch):
    monkeypatch.setattr(settings, "llm_reasoning", True)
    monkeypatch.setattr(settings, "zhipu_api_key", "some-key")
    assert settings.llm_configured is False  # permanently retired


@pytest.mark.asyncio
async def test_derm_kb_answers_even_with_reasoner_env_flags(client, monkeypatch):
    monkeypatch.setattr(settings, "llm_reasoning", True)
    monkeypatch.setattr(settings, "zhipu_api_key", "some-key")
    r = await client.post(
        "/api/clinical",
        json={"messages": [{"role": "doctor", "text": _PSORIASIS_CASE}], "lang": "en"},
    )
    reply = json.loads(r.json()["text"])
    assert reply["differential"]
    assert "psoriasis" in reply["differential"][0]["condition"].lower()


# ── 4: post-generation screen on the small-talk AI reply ─────────────────────


@pytest.mark.asyncio
async def test_hallucinated_drug_in_smalltalk_reply_is_screened(client, ai_on):
    # The model tries to smuggle a clinical statement into a smalltalk reply.
    ai_on.text = "You're welcome! By the way, give Prednisolone 50mg daily for 6 weeks."
    r = await client.post(
        "/api/clinical",
        json={
            "messages": [
                {"role": "doctor", "text": _PSORIASIS_CASE},
                {"role": "ai", "text": "Leading consideration: Psoriasis."},
                {"role": "doctor", "text": "thank you"},
            ],
            "lang": "en",
        },
    )
    reply = json.loads(r.json()["text"])
    assert ai_on.calls  # the AI WAS consulted (legitimate small talk) …
    assert reply["summary"] == _GREETING["en"]  # … but its output was rejected


@pytest.mark.asyncio
async def test_clean_smalltalk_reply_passes_screen(client, ai_on):
    ai_on.text = "You're very welcome — happy to help."
    r = await client.post(
        "/api/clinical",
        json={
            "messages": [
                {"role": "doctor", "text": _PSORIASIS_CASE},
                {"role": "ai", "text": "Leading consideration: Psoriasis."},
                {"role": "doctor", "text": "thank you"},
            ],
            "lang": "en",
        },
    )
    reply = json.loads(r.json()["text"])
    assert reply["summary"] == ai_on.text
    assert reply["aiChat"] is True


# ── file-answerer correctness ────────────────────────────────────────────────


def test_followup_dose_answer_comes_from_files():
    out = kb_answer.answer("what dose of methotrexate should I use?", None, "en")
    assert out is not None
    assert "WEEKLY" in out  # the file's dose text, verbatim
    assert "10-15mg" in out


def test_unanswerable_question_returns_none():
    assert kb_answer.answer("what is the capital of France?", None, "en") is None


def test_zh_alert_colours_surface_in_safety_flags():
    flags = demo_derm._alert_flags({"药品": "测试药", "警示": "红色"}, "zh")
    assert any(f["severity"] == "Major" for f in flags)
    flags = demo_derm._alert_flags({"药品": "测试药", "警示": "黄色"}, "zh")
    assert any(f["severity"] == "Moderate" for f in flags)


def test_drugref_matches_partial_key_tokens():
    out = kb_answer._drugref_lines("what is the max daily dose of insulin?", "en")
    assert out and any("insulin" in ln for ln in out)
    out = kb_answer._drugref_lines("piperacillin renal dosing?", "en")
    assert out and any("piperacillin" in ln for ln in out)
    # A bare form/salt word must not match anything.
    assert kb_answer._drugref_lines("sodium levels?", "en") == []


def test_colloquial_names_resolve_to_the_right_condition():
    # 牛皮癣 (colloquial psoriasis) must NOT match the single-character 癣 (tinea).
    named = kb_answer._named_conditions("牛皮癣用什么药？")
    assert named and named[0]["slug"] == "psoriasis"
    # eczema → Atopic Dermatitis (present in the files under that name).
    named = kb_answer._named_conditions("what is the treatment for eczema?")
    assert named and named[0]["slug"] == "atopic_dermatitis"
    # The full zh name 玫瑰痤疮 (rosacea) must beat the shorter 痤疮 (acne).
    named = kb_answer._named_conditions("玫瑰痤疮的治疗方案")
    assert named and named[0]["slug"] == "rosacea"
    # Bare English words that happen to be unique name tokens must not match.
    assert not kb_answer._named_conditions("why is the ranking fixed?")


def test_zh_drug_question_has_no_duplicate_entries():
    out = kb_answer.answer("甲氨蝶呤的剂量是多少？", None, "zh")
    assert out is not None
    # The EN entry (matched via drug_cn) and its CN parallel must render once.
    assert out.count("甲氨蝶呤片（用于银屑病") <= 1


def test_quicklook_preview_is_file_grounded():
    # A distinctive presentation names a condition and lists file keywords.
    out = demo_derm.preview("silvery scaly plaque on the elbow", "en")
    assert out["diagnoses"], "a distinctive case should surface candidate conditions"
    assert out["diagnoses"][0]["condition"] == "Psoriasis"
    assert out["diagnoses"][0]["icd"] == "L40.9"
    assert 0 < out["diagnoses"][0]["probability"] <= 95
    # Keywords are verbatim key-finding phrases from the KB file.
    assert any("scale" in k.lower() for k in out["keywords"])


def test_quicklook_generic_input_names_no_diagnosis():
    # Colour + symptom alone must NOT guess a condition (esp. a cancer).
    out = demo_derm.preview("red itchy", "en")
    assert out["diagnoses"] == []


def test_quicklook_empty_and_nonclinical():
    assert demo_derm.preview("", "en") == {"keywords": [], "diagnoses": []}
    assert demo_derm.preview("hello there", "en") == {"keywords": [], "diagnoses": []}


def test_quicklook_zh_preview():
    out = demo_derm.preview("银白色鳞屑斑块", "zh")
    assert out["diagnoses"] and out["diagnoses"][0]["condition"] == "银屑病"


@pytest.mark.asyncio
async def test_quicklook_endpoint(client):
    r = await client.post(
        "/api/quicklook",
        json={"text": "comedones and pustules on the face", "lang": "en"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["diagnoses"][0]["condition"] == "Acne Vulgaris"
    assert body["keywords"]


@pytest.mark.asyncio
async def test_quicklook_endpoint_never_persists_or_prescribes(client):
    # The preview must not create a suggestion row or return a treatment plan.
    r = await client.post(
        "/api/quicklook", json={"text": "silvery scaly plaque", "lang": "en"}
    )
    body = r.json()
    assert "treatment" not in body
    assert set(body.keys()) == {"keywords", "diagnoses"}


@pytest.mark.asyncio
async def test_prescriptive_followup_keeps_safety_screened_card(client):
    r = await client.post(
        "/api/clinical",
        json={
            "messages": [
                {"role": "doctor", "text": _PSORIASIS_CASE},
                {"role": "ai", "text": "Leading consideration: Psoriasis."},
                {"role": "doctor", "text": "what should I prescribe?"},
            ],
            "lang": "en",
        },
    )
    reply = json.loads(r.json()["text"])
    # The treatment card (with its safety flags) stands — not a prose bubble.
    assert reply["treatment"] is not None
    assert reply["treatment"]["medications"]
