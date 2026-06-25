"""POST /v2/episodes — continuous-learning capture (spec §4.2, §13).

Every candidate episode passes the automated data-quality pipeline (validate,
de-identify, code-map check) before it is embedded and live-indexed into the KB.
Bad data is quarantined (422), never silently admitted.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.deps import SessionDep, require
from app.engine.embeddings import embed_text
from app.errors import MediSenseError
from app.idempotency import remember, replay
from app.learning.data_quality import validate_episode
from app.learning.registry import snapshot_hash
from app.models import DiagnosisEpisode
from app.schemas import EpisodeIn
from app.security.audit import record_event
from app.security.rbac import Permission

router = APIRouter(prefix="/v2", tags=["episodes"])


@router.post("/episodes")
async def create_episode(
    body: EpisodeIn,
    session: SessionDep,
    user: Annotated[object, Depends(require(Permission.CAPTURE_EPISODE))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    endpoint = "episodes"
    if (cached := await replay(session, idempotency_key, endpoint)) is not None:
        return cached

    quality = validate_episode(body.model_dump(by_alias=False))
    if not quality.ok:
        raise MediSenseError(
            "data_quality_rejected",
            "Episode quarantined by the data-quality pipeline.",
            status_code=422,
            detail={"issues": quality.issues},
        )

    # Embed the de-identified text and live-index it.
    vec = await embed_text(quality.cleaned_text)
    snap = await snapshot_hash(session)
    episode = DiagnosisEpisode(
        symptom_text=quality.cleaned_text,
        diagnosis=body.diagnosis,
        icd=body.icd,
        treatment=body.treatment,
        outcome=float(body.outcome),
        next_best_test=body.next_best_test,
        supporting=body.supporting,
        embedding=vec,
        source="captured",
        deidentified=True,
        snapshot_id=snap,
    )
    session.add(episode)
    await session.flush()
    await record_event(
        session,
        actor=getattr(user, "name", "unknown"),
        role=getattr(user, "role", None),
        action="episode.capture",
        target=f"episode:{episode.id}",
        detail={"diagnosis": body.diagnosis, "outcome": body.outcome, "snapshot": snap},
    )
    result = {"episodeId": episode.id, "indexed": True}
    await remember(session, idempotency_key, endpoint, result)
    await session.commit()
    return result
