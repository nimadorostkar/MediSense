"""Text → vector (spec §6 `embeddings.py`).

Production path: Zhipu `embedding-3` via the provider, with an in-process cache.
Offline path: a deterministic hashing embedder so the whole pipeline runs with
zero external dependencies (dev/SQLite/CI). Both produce unit-norm vectors of
EMBEDDING_DIM so retrieval math is identical either way.
"""

from __future__ import annotations

import hashlib
import math
import re

from app.ai.zhipu import get_zhipu_provider
from app.config import settings
from app.db.base import EMBEDDING_DIM
from app.observability.logging import get_logger

log = get_logger("medisense.embeddings")

_TOKEN_RE = re.compile(r"[a-z0-9一-鿿]+")
_cache: dict[str, list[float]] = {}


def _tokenize(text: str) -> list[str]:
    """Lowercase word/CJK tokenization (Chinese chars are individually salient)."""
    text = text.lower()
    tokens: list[str] = []
    for m in _TOKEN_RE.findall(text):
        if any("一" <= ch <= "鿿" for ch in m):
            tokens.extend(list(m))  # split CJK runs into single characters
        else:
            tokens.append(m)
    return tokens


def _normalize(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0:
        return vec
    return [v / norm for v in vec]


def hashing_embed(text: str) -> list[float]:
    """Deterministic bag-of-features hashing embedder (offline fallback)."""
    vec = [0.0] * EMBEDDING_DIM
    tokens = _tokenize(text)
    if not tokens:
        return vec
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)  # noqa: S324 - non-crypto use
        idx = h % EMBEDDING_DIM
        sign = 1.0 if (h >> 8) & 1 else -1.0
        vec[idx] += sign
    return _normalize(vec)


def _truncate_or_pad(vec: list[float], dim: int = EMBEDDING_DIM) -> list[float]:
    if len(vec) == dim:
        return _normalize(list(vec))
    if len(vec) > dim:
        return _normalize(list(vec[:dim]))
    return _normalize(list(vec) + [0.0] * (dim - len(vec)))


async def embed_text(text: str) -> list[float]:
    return (await embed_texts([text]))[0]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch, caching results. Falls back to hashing on any provider error."""
    out: list[list[float] | None] = [None] * len(texts)
    misses: list[int] = []
    for i, t in enumerate(texts):
        cached = _cache.get(t)
        if cached is not None:
            out[i] = cached
        else:
            misses.append(i)

    if misses:
        provider = get_zhipu_provider()
        miss_texts = [texts[i] for i in misses]
        vectors: list[list[float]] | None = None
        if provider is not None:
            try:
                raw = await provider.embed(miss_texts)
                vectors = [_truncate_or_pad(v) for v in raw]
            except Exception as exc:  # noqa: BLE001 - degrade to local embedder
                log.warning("embed_provider_failed", extra={"error": str(exc)})
                vectors = None
        if vectors is None:
            vectors = [hashing_embed(t) for t in miss_texts]
        for j, i in enumerate(misses):
            _cache[texts[i]] = vectors[j]
            out[i] = vectors[j]

    return [v if v is not None else hashing_embed(texts[k]) for k, v in enumerate(out)]


def embedding_backend() -> str:
    return "zhipu" if (settings.zhipu_api_key and not settings.is_sqlite) else "hashing"
