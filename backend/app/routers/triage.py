"""Triage queue (spec §8). Pilot acuity scorer: transparent, rule-weighted.

GET /v2/triage/queue returns recent encounters ranked by an acuity band derived
from red-flag rules and vitals — the same deterministic signals the clinician can
inspect (spec §8.2 transparency).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..engine import rules as rules_mod
from ..models import Encounter

router = APIRouter(prefix="/v2/triage")


def _acuity(symptom_text: str, vitals: dict) -> tuple[str, list[str]]:
    factors: list[str] = []
    hit = rules_mod.evaluate(symptom_text)
    if hit.red_flag:
        factors.append("red-flag rule fired")
    spo2 = vitals.get("spo2") or vitals.get("SpO2")
    if isinstance(spo2, (int, float)) and spo2 < 92:
        factors.append(f"SpO2 {spo2}%")
    hr = vitals.get("hr") or vitals.get("HR")
    if isinstance(hr, (int, float)) and hr > 110:
        factors.append(f"HR {hr}")
    band = "Critical" if hit.red_flag else ("Urgent" if factors else "Routine")
    return band, factors


@router.get("/queue")
async def queue(limit: int = 20, session: AsyncSession = Depends(get_session)) -> dict:
    rows = (await session.execute(
        select(Encounter).order_by(Encounter.created_at.desc()).limit(limit)
    )).scalars().all()
    items = []
    for e in rows:
        band, factors = _acuity(e.symptom_text, e.vitals or {})
        items.append({"encounterId": e.id, "band": band, "factors": factors,
                      "complaint": (e.symptom_text or "")[:80], "at": e.created_at.isoformat()})
    order = {"Critical": 0, "Urgent": 1, "Routine": 2}
    items.sort(key=lambda x: order.get(x["band"], 9))
    return {"queue": items}
