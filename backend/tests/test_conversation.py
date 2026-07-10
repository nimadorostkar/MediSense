"""Tests for the Gemini/Zhipu conversational layer (engine/conversation.py).

A fake provider stands in for the network so these run offline and deterministic.
They assert: the layer is off unless a key is configured; a clinical answer
(differential/treatment) is rendered ENTIRELY from the KB and is NEVER touched by
the AI — even when the AI layer is on; and only a genuine conversational turn
(greeting/thanks/follow-up question) gets a real AI chat answer.
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


async def test_chat_off_without_key():
    # No key configured in the base test env → layer is inert.
    assert not settings.chat_configured
    assert await conversation.chat_reply([{"role": "doctor", "text": "hi"}], None, "en") is None


async def test_narrate_no_longer_exists():
    # The AI must never narrate a clinical answer — the entry point is removed.
    assert not hasattr(conversation, "narrate")


async def test_chat_reply_uses_history(gemini_on):
    out = await conversation.chat_reply(
        [{"role": "doctor", "text": "why is psoriasis first?"}], {"differential": []}, "en"
    )
    assert out == "Fake grounded narration."
    assert gemini_on.calls[-1][0] == "chat"


async def test_clinical_endpoint_diagnosis_is_kb_only_even_with_ai_on(client, gemini_on):
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
    # Even with the AI layer ON, a clinical answer is rendered ENTIRELY from the
    # KB: the summary is NOT the AI text, and the reply is not flagged aiChat.
    assert reply["summary"] != "Fake grounded narration."
    assert "Psoriasis".lower() in reply["summary"].lower()
    assert not reply.get("aiChat")
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
