"""Idempotency-key support for write endpoints (spec §4.3).

A repeated request carrying the same `Idempotency-Key` returns the stored
result instead of performing the write twice, so client retries are safe.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IdempotencyKey


async def replay(session: AsyncSession, key: str | None, endpoint: str) -> dict | None:
    if not key:
        return None
    res = await session.execute(
        select(IdempotencyKey).where(IdempotencyKey.key == key, IdempotencyKey.endpoint == endpoint)
    )
    row = res.scalars().first()
    return row.response if row else None


async def remember(session: AsyncSession, key: str | None, endpoint: str, response: dict) -> None:
    if not key:
        return
    session.add(IdempotencyKey(key=key, endpoint=endpoint, response=response))
    await session.flush()
