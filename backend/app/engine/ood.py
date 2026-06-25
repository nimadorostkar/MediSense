"""Out-of-distribution detector (spec §6 `ood.py`, §6.6).

Low retrieval similarity (distance-to-manifold proxy) trips a low-confidence /
escalation path: a widened, clearly-flagged differential rather than a confident
guess on a patient unlike anything in the knowledge base.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings
from app.engine.vector_index import Neighbor


@dataclass
class OODResult:
    is_ood: bool
    top_similarity: float
    reason: str = ""


def detect_ood(neighbors: list[Neighbor]) -> OODResult:
    if not neighbors:
        return OODResult(True, 0.0, "no_similar_cases")
    top = max(n.similarity for n in neighbors)
    if top < settings.ood_similarity_floor:
        return OODResult(
            True, top, "low_similarity — patient unlike anything in the knowledge base"
        )
    return OODResult(False, top, "")
