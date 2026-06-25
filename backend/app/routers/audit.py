"""Audit trail query (spec §17.1 /audit/events)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..models import AuditEvent

router = APIRouter(prefix="/v2/audit")


@router.get("/events")
async def events(limit: int = 50, session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(
        select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    )).scalars().all()
    return {"events": [{
        "id": e.id, "actor": e.actor, "action": e.action, "target": e.target,
        "detail": e.detail, "hash": e.hash[:12], "at": e.created_at.isoformat(),
    } for e in rows]}
