"""Nearest-neighbour retrieval (spec §6 `vector_index.py`).

Production: pgvector ANN (`<=>` cosine distance, HNSW index from the migration).
Fallback: in-process cosine over the episode table (SQLite / pgvector absent).
Both return `(episode, similarity)` pairs with similarity in [0, 1].
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DiagnosisEpisode


@dataclass
class Neighbor:
    episode: DiagnosisEpisode
    similarity: float


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def _pgvector_supported(session: AsyncSession) -> bool:
    if settings.is_sqlite:
        return False
    try:
        res = await session.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        return res.first() is not None
    except Exception:  # pragma: no cover
        return False


async def retrieve(
    session: AsyncSession, query_vec: list[float], k: int | None = None
) -> list[Neighbor]:
    k = k or settings.retrieval_k

    if await _pgvector_supported(session):
        try:
            # pgvector wants a literal like '[0.1,0.2,...]'; cast to ::vector so
            # the cosine-distance operator resolves. similarity = 1 - distance.
            qlit = "[" + ",".join(repr(float(x)) for x in query_vec) + "]"
            stmt = text(
                "SELECT id, 1 - (embedding <=> (:q)::vector) AS sim "
                "FROM diagnosis_episodes WHERE embedding IS NOT NULL "
                "ORDER BY embedding <=> (:q)::vector LIMIT :k"
            ).bindparams(q=qlit, k=k)
            rows = (await session.execute(stmt)).all()
            ids = [r[0] for r in rows]
            sims = {r[0]: float(r[1]) for r in rows}
            eps = (
                (
                    await session.execute(
                        select(DiagnosisEpisode).where(DiagnosisEpisode.id.in_(ids))
                    )
                )
                .scalars()
                .all()
            )
            by_id = {e.id: e for e in eps}
            return [Neighbor(by_id[i], sims[i]) for i in ids if i in by_id]
        except Exception:  # pragma: no cover - fall back to in-process
            await session.rollback()

    # In-process cosine over all episodes (pilot scale).
    eps = (await session.execute(select(DiagnosisEpisode))).scalars().all()
    scored = [Neighbor(e, cosine(query_vec, e.embedding)) for e in eps if e.embedding]
    scored.sort(key=lambda n: n.similarity, reverse=True)
    return scored[:k]
