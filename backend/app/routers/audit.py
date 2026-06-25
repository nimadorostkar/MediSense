"""GET /v2/audit/events — RBAC-scoped, tamper-evident audit query (spec §4.2,
§18.3). Export is limited to Admin/Safety/IT. Includes a chain-integrity check.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.deps import SessionDep, require
from app.models import AuditEvent
from app.security.audit import verify_chain
from app.security.rbac import Permission

router = APIRouter(prefix="/v2", tags=["audit"])


@router.get("/audit/events")
async def audit_events(
    session: SessionDep,
    user: Annotated[object, Depends(require(Permission.EXPORT_AUDIT))],
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    rows = (
        (await session.execute(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(limit)))
        .scalars()
        .all()
    )
    ok, broken = await verify_chain(session)
    events = [
        {
            "seq": e.seq,
            "actor": e.actor,
            "role": e.role,
            "action": e.action,
            "target": e.target,
            "detail": e.detail,
            "prevHash": e.prev_hash,
            "hash": e.hash,
            "ts": e.ts.isoformat() if e.ts else None,
        }
        for e in rows
    ]
    return {"events": events, "chainValid": ok, "brokenAtSeq": broken}
