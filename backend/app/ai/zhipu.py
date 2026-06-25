"""Zhipu GLM provider — chat (reasoning) + embeddings via the OpenAI-compatible
API (spec §6.2).

China base URL default: https://open.bigmodel.cn/api/paas/v4 (configurable).
Auth via ZHIPU_API_KEY. Defaults: chat `glm-4.6`, embedding `embedding-3` — kept
in config; verify against Zhipu docs at build time. Resilience: bounded timeout
and retries with backoff; callers fall back to the deterministic pipeline on
failure (spec §6.2 / §7 degraded mode).

NOTE (build-time verification): model identifiers are config-driven. As of this
build the pilot defaults are GLM `glm-4.6` and `embedding-3`; update the env if
Zhipu's current identifiers differ.
"""

from __future__ import annotations

import asyncio

from app.config import settings
from app.observability.logging import get_logger
from app.observability.metrics import DEGRADED_MODE

log = get_logger("medisense.zhipu")

_MAX_RETRIES = 2
_BACKOFF_BASE = 0.4


class ZhipuError(RuntimeError):
    pass


class ZhipuProvider:
    """Thin wrapper over the `openai` SDK pointed at the Zhipu base URL."""

    name = "zhipu"

    def __init__(self) -> None:
        if not settings.zhipu_api_key:
            raise ZhipuError("ZHIPU_API_KEY not configured")
        # Imported lazily so the package is optional when running offline.
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            api_key=settings.zhipu_api_key,
            base_url=settings.zhipu_base_url,
            timeout=settings.llm_timeout_seconds,
            max_retries=0,  # we manage retries/backoff ourselves
        )

    async def _with_retries(self, coro_factory, component: str):
        last: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return await asyncio.wait_for(
                    coro_factory(), timeout=settings.llm_timeout_seconds
                )
            except Exception as exc:  # noqa: BLE001 - resilience boundary
                last = exc
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_BACKOFF_BASE * (2**attempt))
        DEGRADED_MODE.labels(component=component).inc()
        log.warning("zhipu_call_failed", extra={"component": component, "error": str(last)})
        raise ZhipuError(str(last))

    async def embed(self, texts: list[str]) -> list[list[float]]:
        async def _call():
            return await self._client.embeddings.create(
                model=settings.embedding_model, input=texts
            )

        resp = await self._with_retries(_call, "embeddings")
        return [d.embedding for d in resp.data]

    async def reason(self, system: str, user: str, *, max_tokens: int) -> str:
        async def _call():
            return await self._client.chat.completions.create(
                model=settings.llm_chat_model,
                max_tokens=max_tokens,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )

        resp = await self._with_retries(_call, "reasoner")
        return resp.choices[0].message.content or ""


def get_zhipu_provider() -> ZhipuProvider | None:
    """Return a live provider only if a key is present, else None (offline)."""
    if not settings.zhipu_api_key:
        return None
    try:
        return ZhipuProvider()
    except Exception as exc:  # noqa: BLE001
        log.warning("zhipu_init_failed", extra={"error": str(exc)})
        return None
