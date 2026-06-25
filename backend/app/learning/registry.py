"""MLOps seams: KB snapshots, model registry, offline eval-gate runner
(spec §14).

The registry and the eval-gate runner are real and deterministic; the heavy
model training is an out-of-band, reproducible script. A model release cannot be
*authored and approved by the same role* (separation of duties, spec §8) — that
constraint is enforced by RBAC at the approval endpoint.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import DiagnosisEpisode


@dataclass
class GateResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class EvalReport:
    model_version: str
    snapshot_id: str
    gates: list[GateResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(g.passed for g in self.gates)


async def snapshot_hash(session: AsyncSession) -> str:
    """Deterministic hash identifying the current KB snapshot (spec §13.5)."""
    rows = (
        await session.execute(
            select(
                DiagnosisEpisode.id, DiagnosisEpisode.diagnosis, DiagnosisEpisode.outcome
            ).order_by(DiagnosisEpisode.id)
        )
    ).all()
    payload = json.dumps([[r[0], r[1], round(r[2], 4)] for r in rows], sort_keys=True)
    return "kb-" + hashlib.sha256(payload.encode()).hexdigest()[:16]


def current_versions() -> dict:
    return {
        "modelVersion": settings.model_version,
        "ruleSetVersion": settings.ruleset_version,
        "drugRefVersion": settings.drugref_version,
        "promptVersion": settings.prompt_version,
        "embeddingVersion": settings.embedding_version,
    }


async def run_eval_gates(session: AsyncSession) -> EvalReport:
    """Offline eval-gate runner (spec §14.4). The safety golden suite is a hard
    gate executed by the test suite; here we run the data/availability gates that
    can be checked at runtime."""
    from app.engine.rules import RED_FLAG_RULES

    n_episodes = len((await session.execute(select(DiagnosisEpisode.id))).all())
    snap = await snapshot_hash(session)
    gates = [
        GateResult("kb_nonempty", n_episodes > 0, f"{n_episodes} episodes"),
        GateResult(
            "rules_loaded", len(RED_FLAG_RULES) > 0, f"{len(RED_FLAG_RULES)} red-flag rules"
        ),
        GateResult("versions_stamped", all(current_versions().values()), "all versions present"),
    ]
    return EvalReport(model_version=settings.model_version, snapshot_id=snap, gates=gates)
