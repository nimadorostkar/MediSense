"""Seed loader — embeds the illustrative KB on first start (spec §6.3).

Idempotent: skips if episodes already exist. Each episode is embedded (Zhipu
when available, hashing fallback otherwise) and stamped with the KB snapshot id.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.engine.embeddings import embed_texts
from app.models import DiagnosisEpisode
from app.observability.logging import get_logger

log = get_logger("medisense.seed")
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_SEED_LOCK_KEY = 727274  # arbitrary constant for the pg advisory lock


async def episode_count(session: AsyncSession) -> int:
    res = await session.execute(select(func.count()).select_from(DiagnosisEpisode))
    return int(res.scalar_one())


async def seed_episodes(session: AsyncSession) -> int:
    """Load data/episodes.json if the KB is empty. Returns episodes loaded.

    Concurrency-safe: with multiple Gunicorn workers booting at once, a Postgres
    transaction-level advisory lock serializes them so the seed runs exactly once
    (the losers see a non-empty KB and skip). SQLite dev is single-process."""
    if not settings.is_sqlite:
        # Held until this transaction commits — serializes concurrent workers.
        await session.execute(text("SELECT pg_advisory_xact_lock(:k)").bindparams(k=_SEED_LOCK_KEY))
    if await episode_count(session) > 0:
        return 0

    with open(DATA_DIR / "episodes.json", encoding="utf-8") as f:
        payload = json.load(f)
    snapshot_id = payload.get("_meta", {}).get("snapshot_id", "kb-seed")
    episodes = payload["episodes"]

    texts = [e["symptomText"] for e in episodes]
    vectors = await embed_texts(texts)

    for e, vec in zip(episodes, vectors, strict=True):
        session.add(
            DiagnosisEpisode(
                symptom_text=e["symptomText"],
                diagnosis=e["diagnosis"],
                icd=e.get("icd"),
                treatment=e.get("treatment", {}),
                outcome=float(e.get("outcome", 0.0)),
                next_best_test=e.get("nextBestTest"),
                supporting=e.get("supporting", []),
                embedding=vec,
                source="seed",
                deidentified=True,
                snapshot_id=snapshot_id,
            )
        )
    await session.commit()
    log.info("seed_loaded", extra={"episodes": len(episodes), "snapshot": snapshot_id})
    return len(episodes)
