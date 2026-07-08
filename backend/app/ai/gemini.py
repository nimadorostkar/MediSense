"""Google Gemini provider — conversational chat + grounded reasoning (spec §6.2).

Gemini has a generous free tier (Google AI Studio key), which makes it a good fit
for the pilot's natural-language layer while the deterministic hybrid engine
still owns every clinical fact. This talks to the REST `generateContent` endpoint
directly over httpx (no extra SDK), with the same bounded-timeout / retry /
degrade-to-offline resilience contract as the Zhipu provider.

Scope: Gemini powers the *language* (conversational summaries + follow-up chat),
never the diagnosis, ranking, dosing, or safety screen — those stay grounded in
the KB and rules layers. A downed key or failed call simply drops back to the
deterministic templated text.
"""

from __future__ import annotations

import asyncio

import httpx

from app.config import settings
from app.observability.logging import get_logger
from app.observability.metrics import DEGRADED_MODE

log = get_logger("medisense.gemini")

_MAX_RETRIES = 2
_BACKOFF_BASE = 0.4


class GeminiError(RuntimeError):
    pass


class GeminiProvider:
    """Thin async wrapper over the Gemini `generateContent` REST API."""

    name = "gemini"

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise GeminiError("GEMINI_API_KEY not configured")
        self._key = settings.gemini_api_key
        self._base = settings.gemini_base_url.rstrip("/")
        self._model = settings.gemini_model

    async def _generate(self, payload: dict, component: str) -> str:
        url = f"{self._base}/models/{self._model}:generateContent"
        last: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                    resp = await client.post(
                        url, params={"key": self._key}, json=payload
                    )
                    resp.raise_for_status()
                    data = resp.json()
                return _first_text(data)
            except Exception as exc:  # noqa: BLE001 - resilience boundary
                last = exc
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_BACKOFF_BASE * (2**attempt))
        DEGRADED_MODE.labels(component=component).inc()
        log.warning("gemini_call_failed", extra={"component": component, "error": str(last)})
        raise GeminiError(str(last))

    async def reason(self, system: str, user: str, *, max_tokens: int) -> str:
        """Single-shot grounded call (LLMProvider protocol)."""
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens},
        }
        return await self._generate(payload, "reasoner")

    async def chat(
        self,
        messages: list[dict],
        *,
        system: str,
        max_tokens: int = 640,
        temperature: float = 0.6,
    ) -> str:
        """Multi-turn conversational call. `messages` = [{role: user|ai, text}]."""
        contents = []
        for m in messages:
            text = (m.get("text") or "").strip()
            if not text:
                continue
            role = "user" if (m.get("role") or "").lower() in ("doctor", "user") else "model"
            contents.append({"role": role, "parts": [{"text": text}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Hello"}]}]
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        return await self._generate(payload, "conversation")


def _first_text(data: dict) -> str:
    """Extract the model text from a generateContent response (defensively)."""
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts).strip()


def get_gemini_provider() -> GeminiProvider | None:
    """Return a live provider only if a key is present, else None (offline)."""
    if not settings.gemini_api_key:
        return None
    try:
        return GeminiProvider()
    except Exception as exc:  # noqa: BLE001
        log.warning("gemini_init_failed", extra={"error": str(exc)})
        return None
