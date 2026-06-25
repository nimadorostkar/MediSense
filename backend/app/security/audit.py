"""Immutable, hash-chained audit trail (spec §1.6, §18.3).

Each event stores `prev_hash` and its own `hash = sha256(prev_hash || canonical
fields)`, so any tampering breaks the chain and is detectable. Append-only:
nothing here updates or deletes an event. The timestamp used in the hash is
normalized to whole-second UTC so it round-trips identically on SQLite and
Postgres.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditEvent

GENESIS = "0" * 64


def _iso(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0).isoformat() + "Z"


def compute_hash(
    prev_hash: str, actor: str, action: str, target: str | None, detail: dict, ts: str
) -> str:
    payload = json.dumps(
        {
            "prev": prev_hash,
            "actor": actor,
            "action": action,
            "target": target,
            "detail": detail,
            "ts": ts,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _last_event(session: AsyncSession) -> AuditEvent | None:
    res = await session.execute(select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(1))
    return res.scalars().first()


async def record_event(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    role: str | None = None,
    target: str | None = None,
    detail: dict | None = None,
) -> AuditEvent:
    detail = detail or {}
    prev = await _last_event(session)
    prev_hash = prev.hash if prev else GENESIS
    seq = (prev.seq + 1) if prev else 1
    ts_dt = datetime.now(timezone.utc).replace(microsecond=0)
    ts_str = _iso(ts_dt)
    h = compute_hash(prev_hash, actor, action, target, detail, ts_str)
    event = AuditEvent(
        seq=seq,
        actor=actor,
        role=role,
        action=action,
        target=target,
        detail=detail,
        prev_hash=prev_hash,
        hash=h,
        ts=ts_dt,
    )
    session.add(event)
    await session.flush()
    return event


async def verify_chain(session: AsyncSession) -> tuple[bool, int | None]:
    """Recompute the whole chain; returns (ok, first_broken_seq)."""
    events = (
        await session.execute(select(AuditEvent).order_by(AuditEvent.seq.asc()))
    ).scalars().all()
    prev_hash = GENESIS
    for e in events:
        expected = compute_hash(prev_hash, e.actor, e.action, e.target, e.detail, _iso(e.ts))
        if e.prev_hash != prev_hash or e.hash != expected:
            return False, e.seq
        prev_hash = e.hash
    return True, None
