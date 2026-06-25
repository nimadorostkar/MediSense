"""Knowledge-base capture (spec §17.1 /episodes, §13.2 continuous learning).

POST /v2/episodes captures a completed, outcome-labelled episode, embeds it,
persists it, and live-updates the retrieval index — so the next patient benefits.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from .. import audit_util, seed
from ..db import get_session
from ..engine.embeddings import get_embedder
from ..models import DiagnosisEpisode

router = APIRouter(prefix="/v2/episodes")


class EpisodeIn(BaseModel):
    symptomText: str
    diagnosis: str
    icd: str = ""
    department: str | None = None
    treatment: dict = {}
    outcome: float = 1.0
    nextBestTest: str | None = None


@router.post("")
async def add_episode(body: EpisodeIn, session: AsyncSession = Depends(get_session)) -> dict:
    emb = get_embedder().embed(body.symptomText).tolist()
    epi = DiagnosisEpisode(
        symptom_text=body.symptomText, diagnosis=body.diagnosis, icd=body.icd,
        department=body.department, treatment=body.treatment, outcome=body.outcome,
        next_best_test=body.nextBestTest, embedding=emb,
    )
    session.add(epi)
    await audit_util.record(session, "system", "episode_captured", epi.id,
                            {"diagnosis": body.diagnosis})
    await session.commit()
    await seed.rebuild_index(session)  # live-update retrieval (pilot scale)
    return {"episodeId": epi.id, "indexed": True}
