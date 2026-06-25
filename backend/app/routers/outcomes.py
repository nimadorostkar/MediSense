"""POST /v2/encounters/{id}/outcome — structured recovery outcome (spec §4.2).

Captures the recovery signal that lets the engine weight plans that actually
worked, and (when a confirmed diagnosis exists) feeds a learning episode back
into the KB.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.deps import SessionDep, require
from app.engine.embeddings import embed_text
from app.errors import NotFoundError
from app.models import Decision, DiagnosisEpisode, Encounter, OutcomeRecord
from app.schemas import OutcomeIn
from app.security.audit import record_event
from app.security.rbac import Permission

router = APIRouter(prefix="/v2", tags=["outcomes"])


@router.post("/encounters/{encounter_id}/outcome")
async def capture_outcome(
    encounter_id: str,
    body: OutcomeIn,
    session: SessionDep,
    user: Annotated[object, Depends(require(Permission.CAPTURE_OUTCOME))],
) -> dict:
    enc = await session.get(Encounter, encounter_id)
    if enc is None or enc.deleted:
        raise NotFoundError("encounter")

    record = OutcomeRecord(
        encounter_id=encounter_id,
        scale=float(body.scale),
        readmission_flag=body.readmission_flag,
        follow_up_status=body.follow_up_status,
    )
    session.add(record)

    # If the encounter has a confirmed diagnosis, close the learning loop.
    indexed = False
    decision = (
        await session.execute(
            select(Decision).where(Decision.encounter_id == encounter_id).order_by(Decision.created_at.desc())
        )
    ).scalars().first()
    if decision and enc.symptom_text:
        vec = await embed_text(enc.symptom_text)
        session.add(
            DiagnosisEpisode(
                symptom_text=enc.symptom_text,
                diagnosis=decision.confirmed_diagnosis,
                icd=decision.icd,
                treatment={},
                outcome=float(body.scale),
                source="outcome",
                embedding=vec,
                deidentified=True,
            )
        )
        indexed = True

    await record_event(
        session,
        actor=getattr(user, "name", "unknown"),
        role=getattr(user, "role", None),
        action="outcome.capture",
        target=f"encounter:{encounter_id}",
        detail={"scale": body.scale, "readmission": body.readmission_flag, "indexed": indexed},
    )
    await session.commit()
    return {"encounterId": encounter_id, "ok": True, "indexed": indexed}
