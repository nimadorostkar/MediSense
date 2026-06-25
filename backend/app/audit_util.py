"""Hash-chained audit writer (spec §18.3) — tamper-evident append-only trail."""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

from .models import AuditEvent


async def record(session, actor: str, action: str, target: str | None, detail: dict) -> None:
    last = (
        await session.execute(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(1))
    ).scalars().first()
    prev_hash = last.hash if last else None
    body = json.dumps({"actor": actor, "action": action, "target": target,
                       "detail": detail, "prev": prev_hash}, sort_keys=True, default=str)
    digest = hashlib.sha256(body.encode()).hexdigest()
    session.add(AuditEvent(actor=actor, action=action, target=target,
                           detail=detail, prev_hash=prev_hash, hash=digest))
