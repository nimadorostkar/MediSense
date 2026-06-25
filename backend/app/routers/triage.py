"""GET /v2/triage/queue — live, acuity-ranked patient queue (spec §4.2, §8).

`scorer=offline` returns the queue in manual order with a banner (degraded mode,
spec §7) so the board stays visible even when the scorer is down.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.deps import SessionDep, require
from app.engine.enrich import enrich
from app.engine.triage import ROUTINE, compute_acuity
from app.models import Encounter
from app.security.rbac import Permission

router = APIRouter(prefix="/v2", tags=["triage"])

_BAND_ORDER = {"CRITICAL": 0, "URGENT": 1, "ROUTINE": 2, "UNSCORED": 3}


@router.get("/triage/queue")
async def triage_queue(
    session: SessionDep,
    user: Annotated[object, Depends(require(Permission.VIEW_TRIAGE))],
    limit: int = Query(20, ge=1, le=100),
    scorer: str = Query("online"),
) -> dict:
    rows = (
        await session.execute(
            select(Encounter)
            .where(Encounter.deleted == False, Encounter.status.in_(["open", "diagnosed"]))  # noqa: E712
            .order_by(Encounter.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()

    degraded = scorer == "offline"
    queue = []
    for enc in rows:
        item = {
            "encounterId": enc.id,
            "age": enc.age,
            "sex": enc.sex,
            "chiefComplaint": enc.chief_complaint or (enc.symptom_text[:60] if enc.symptom_text else ""),
            "vitals": enc.vitals,
        }
        if degraded:
            item.update({"band": "UNSCORED", "score": None, "factors": {}})
        else:
            patient = enrich(enc.symptom_text, {"vitals": enc.vitals, "age": enc.age, "sex": enc.sex})
            item.update(compute_acuity(patient))
        queue.append(item)

    if not degraded:
        queue.sort(key=lambda q: (_BAND_ORDER.get(q["band"], 9), -(q.get("score") or 0)))

    return {
        "queue": queue,
        "degradedMode": degraded,
        "banner": "Triage scorer offline — manual ordering" if degraded else "",
        "counts": {
            b: sum(1 for q in queue if q.get("band") == b)
            for b in ("CRITICAL", "URGENT", ROUTINE)
        },
    }
