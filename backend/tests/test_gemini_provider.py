"""Validate the Gemini REST wiring without hitting the network.

A fake httpx client captures the outgoing request so we can assert the endpoint,
API-key param, payload shape, and response parsing are correct — the part that
can't be exercised offline otherwise.
"""

from __future__ import annotations

import pytest

from app.ai import gemini
from app.config import settings

pytestmark = pytest.mark.asyncio


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._p


class _FakeClient:
    last: tuple = ()

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, params=None, json=None):
        _FakeClient.last = (url, params, json)
        return _Resp({"candidates": [{"content": {"parts": [{"text": "Hello, doctor."}]}}]})


@pytest.fixture
def fake_http(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "gemini-2.0-flash")
    monkeypatch.setattr(gemini.httpx, "AsyncClient", _FakeClient)


async def test_reason_builds_request_and_parses(fake_http):
    provider = gemini.GeminiProvider()
    text = await provider.reason("system prompt", "user prompt", max_tokens=128)
    assert text == "Hello, doctor."
    url, params, payload = _FakeClient.last
    assert url.endswith("/models/gemini-2.0-flash:generateContent")
    assert params == {"key": "test-key"}
    assert payload["systemInstruction"]["parts"][0]["text"] == "system prompt"
    assert payload["contents"][0]["role"] == "user"
    assert payload["generationConfig"]["maxOutputTokens"] == 128


async def test_chat_maps_roles(fake_http):
    provider = gemini.GeminiProvider()
    text = await provider.chat(
        [{"role": "doctor", "text": "hi"}, {"role": "ai", "text": "hello"}],
        system="sys",
        max_tokens=64,
    )
    assert text == "Hello, doctor."
    _, _, payload = _FakeClient.last
    roles = [c["role"] for c in payload["contents"]]
    assert roles == ["user", "model"]  # doctor→user, ai→model


async def test_provider_absent_without_key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", None)
    assert gemini.get_gemini_provider() is None
