"""AI provider selection.

`get_chat_provider()` resolves the conversational / reasoning provider from
config: Gemini (free tier) is preferred when a key is present, Zhipu otherwise.
Returns None when no key is configured, so the deterministic pipeline stands.
Embeddings are intentionally not routed here — they stay on their own provider
so the retrieval index isn't split across incompatible vector spaces.
"""

from __future__ import annotations

from app.config import settings
from app.observability.logging import get_logger

log = get_logger("medisense.ai")


def get_chat_provider():
    """Return the active chat/reasoning provider, or None if none is configured."""
    choice = (settings.llm_provider or "auto").lower()

    if choice in ("auto", "gemini") and settings.gemini_api_key:
        from app.ai.gemini import get_gemini_provider

        provider = get_gemini_provider()
        if provider is not None:
            return provider

    if choice in ("auto", "zhipu") and settings.zhipu_api_key:
        from app.ai.zhipu import get_zhipu_provider

        return get_zhipu_provider()

    return None


def chat_provider_name() -> str | None:
    """Name of the provider that would be used ('gemini'|'zhipu'|None)."""
    choice = (settings.llm_provider or "auto").lower()
    if choice in ("auto", "gemini") and settings.gemini_api_key:
        return "gemini"
    if choice in ("auto", "zhipu") and settings.zhipu_api_key:
        return "zhipu"
    return None
