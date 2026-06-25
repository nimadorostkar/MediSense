"""Active-learning queue (spec §13.3).

Physician overrides and high-uncertainty / OOD cases are the highest-value
training signal; they are routed to the Safety/ML review queue with a priority.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ReviewItem


async def enqueue_review(
    session: AsyncSession,
    *,
    reason: str,
    encounter_id: str | None,
    priority: float,
    detail: dict | None = None,
) -> ReviewItem:
    item = ReviewItem(
        encounter_id=encounter_id,
        reason=reason,
        priority=priority,
        detail=detail or {},
        status="open",
    )
    session.add(item)
    await session.flush()
    return item
