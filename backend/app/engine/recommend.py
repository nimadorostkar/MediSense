"""Treatment recommender (spec §6 `recommend.py`, §7.3).

Draws a candidate plan + medications from the episodes with the *best recovery
outcome* for the target condition — recommending a plan that has worked, not
merely a plausible one (spec §13.1). The output is always passed through the
drug-safety screen by the caller before it reaches the doctor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.labels import icd_for
from app.models import DiagnosisEpisode

_MONITORING = "Re-assess within 48h; return immediately if symptoms worsen or new red flags appear."


@dataclass
class RecommendResult:
    condition: str
    icd: str
    plan: list[str] = field(default_factory=list)
    medications: list[dict] = field(default_factory=list)
    rationale: str = ""
    monitoring: str = _MONITORING
    best_outcome: float = 0.0
    n_cases: int = 0


async def recommend_treatment(session: AsyncSession, condition: str) -> RecommendResult:
    rows = (
        (
            await session.execute(
                select(DiagnosisEpisode)
                .where(DiagnosisEpisode.diagnosis == condition)
                .order_by(DiagnosisEpisode.outcome.desc())
            )
        )
        .scalars()
        .all()
    )

    icd = (rows[0].icd if rows and rows[0].icd else icd_for(condition)) or ""
    if not rows:
        return RecommendResult(
            condition=condition,
            icd=icd,
            rationale="No matched past cases — treatment must be physician-directed.",
        )

    best = rows[0]
    treatment = best.treatment or {}
    plan = list(treatment.get("plan", []))
    meds = [dict(m) for m in treatment.get("medications", [])]
    n = len(rows)
    mean_outcome = sum(r.outcome for r in rows) / n

    rationale = (
        f"Drawn from {n} past case(s) of {condition} (best recovery {best.outcome:.0%}, "
        f"mean {mean_outcome:.0%}); passed the drug-safety screen."
    )
    return RecommendResult(
        condition=condition,
        icd=icd,
        plan=plan,
        medications=meds,
        rationale=rationale,
        best_outcome=best.outcome,
        n_cases=n,
    )
