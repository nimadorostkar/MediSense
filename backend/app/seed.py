"""Seed the knowledge base and build the retrieval index.

On startup: if the episode table is empty, load the illustrative seed episodes,
compute embeddings, and persist them. Then load all episodes into the in-memory
vector index. New episodes captured via POST /v2/episodes are added the same way,
realizing the continuous-learning loop (spec §13.2) at pilot scale.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from .db import SessionLocal
from .engine.embeddings import get_embedder
from .engine.vector_index import get_index
from .models import DiagnosisEpisode

_SEED_PATH = Path(__file__).resolve().parent / "data" / "episodes.json"


async def seed_if_empty() -> int:
    embedder = get_embedder()
    async with SessionLocal() as session:
        existing = (await session.execute(select(DiagnosisEpisode))).scalars().all()
        if not existing:
            rows = json.loads(_SEED_PATH.read_text(encoding="utf-8"))
            for r in rows:
                emb = embedder.embed(r["symptom_text"]).tolist()
                session.add(DiagnosisEpisode(
                    symptom_text=r["symptom_text"], department=r.get("department"),
                    diagnosis=r["diagnosis"], icd=r.get("icd", ""),
                    treatment=r.get("treatment", {}), outcome=float(r.get("outcome", 1.0)),
                    red_flags=r.get("red_flags", []), next_best_test=r.get("next_best_test"),
                    embedding=emb,
                ))
            await session.commit()
        await rebuild_index(session)
    return get_index().size


async def rebuild_index(session) -> None:
    episodes = (await session.execute(select(DiagnosisEpisode))).scalars().all()
    payload = [{
        "id": e.id, "embedding": e.embedding, "diagnosis": e.diagnosis, "icd": e.icd,
        "treatment": e.treatment, "outcome": e.outcome, "next_best_test": e.next_best_test,
        "symptom_text": e.symptom_text, "department": e.department,
    } for e in episodes if e.embedding]
    get_index().build(payload)
