"""Tests for the Gemini/Zhipu conversational layer (engine/conversation.py).

A fake provider stands in for the network so these run offline and deterministic.
They assert: the layer is off unless a key is configured; when on, the natural-
language summary is upgraded but the grounded differential/treatment/safety are
never touched; and a non-diagnostic turn gets a real chat answer.
"""

from __future__ import annotations

import json

import pytest

from app.config import settings
from app.engine import conversation

pytestmark = pytest.mark.asyncio


class _FakeProvider:
    name = "fake"

    def __init__(self, text: str = "Fake grounded narration."):
        self.text = text
        self.calls: list[tuple] = []

    async def reason(self, system: str, user: str, *, max_tokens: int) -> str:
        self.calls.append(("reason", system, user))
        return self.text

    async def chat(self, messages, *, system, max_tokens=480, temperature=0.6) -> str:
        self.calls.append(("chat", system, messages))
        return self.text


@pytest.fixture
def gemini_on(monkeypatch):
    """Turn the conversational layer on with a fake provider (no network)."""
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "conversational_ai", True)
    monkeypatch.setattr(settings, "llm_provider", "auto")
    fake = _FakeProvider()
    monkeypatch.setattr(conversation, "get_chat_provider", lambda: fake)
    return fake


async def test_narrate_off_without_key():
    # No key configured in the base test env → layer is inert.
    assert not settings.chat_configured
    assert await conversation.narrate({"differential": [{"condition": "X"}]}, "en") is None
    assert await conversation.chat_reply([{"role": "doctor", "text": "hi"}], None, "en") is None


async def test_narrate_returns_grounded_prose(gemini_on):
    reply = {
        "redFlag": "",
        "differential": [
            {"condition": "Psoriasis", "icd": "L40.9", "probability": 74, "confidence": "High", "because": "silvery scales"}
        ],
        "nextBestTest": "CBC",
        "treatment": {"bestDiagnosis": "Psoriasis", "medications": [{"drug": "Calcipotriol", "dose": "BID"}], "safety": []},
    }
    out = await conversation.narrate(reply, "en")
    assert out == "Fake grounded narration."
    # The fact sheet handed to the model included the grounded facts.
    _, _system, user = gemini_on.calls[-1]
    assert "Psoriasis" in user and "Calcipotriol" in user


async def test_chat_reply_uses_history(gemini_on):
    out = await conversation.chat_reply(
        [{"role": "doctor", "text": "why is psoriasis first?"}], {"differential": []}, "en"
    )
    assert out == "Fake grounded narration."
    assert gemini_on.calls[-1][0] == "chat"


async def test_clinical_endpoint_narrates_when_on(client, gemini_on):
    r = await client.post(
        "/api/clinical",
        json={
            "messages": [
                {"role": "doctor", "text": "well demarcated erythematous plaques with silvery "
                 "scales on the extensor elbows and scalp"}
            ],
            "lang": "en",
        },
    )
    reply = json.loads(r.json()["text"])
    # Summary is the AI narration; the grounded differential is unchanged.
    assert reply["summary"] == "Fake grounded narration."
    assert reply["aiChat"] is True
    assert reply["differential"] and "psoriasis" in reply["differential"][0]["condition"].lower()
    assert reply["requiresPhysicianConfirmation"] is True


async def test_clinical_endpoint_chat_for_non_diagnostic_turn(client, gemini_on):
    r = await client.post(
        "/api/clinical",
        json={"messages": [{"role": "doctor", "text": "thank you"}], "lang": "en"},
    )
    reply = json.loads(r.json()["text"])
    assert reply["summary"] == "Fake grounded narration."
    assert reply["differential"] == []
    assert reply["aiChat"] is True
