"""Provider abstraction so the model is swappable by config (spec §6.2).

`LLMProvider` and `EmbeddingProvider` are the only surfaces the engine depends
on. `ZhipuProvider` (zhipu.py) implements both against Zhipu's OpenAI-compatible
API. A null/offline provider keeps the deterministic pipeline fully functional
when no key is present.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    name: str

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""
        ...


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    async def reason(self, system: str, user: str, *, max_tokens: int) -> str:
        """Grounded reasoning call; returns raw model text (JSON contract)."""
        ...
