"""Classifier + calibrator (spec §12.4).

Pilot implementation: an outcome-weighted k-NN vote over retrieved episodes.
Each neighbour contributes (similarity × recovery_outcome) to its diagnosis;
scores are normalized into probabilities and temperature-calibrated so they read
as honest confidences rather than over-spiked softmax. This is the documented
seam for a gradient-boosted/neural ensemble (§12.4) — same inputs and outputs.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from .vector_index import Neighbor

# Calibration temperature (>1 softens; re-fit per release in production, §12.4).
_TEMPERATURE = 1.15


@dataclass
class Candidate:
    condition: str
    icd: str
    probability: float           # 0..1, calibrated
    raw_weight: float
    similar_cases: int
    outcomes: dict               # {"improved": x, "readmission_30d": y}
    next_best_test: str | None
    treatment: dict
    supporting_episode_ids: list[str]


def classify(neighbors: list[Neighbor]) -> list[Candidate]:
    if not neighbors:
        return []

    by_dx: dict[str, dict] = defaultdict(
        lambda: {
            "weight": 0.0, "icd": "", "count": 0, "improved": [],
            "readmit": [], "tests": defaultdict(float), "treatment": {}, "ids": [],
        }
    )

    for n in neighbors:
        p = n.payload
        dx = p["diagnosis"]
        outcome = float(p.get("outcome", 1.0))
        # Outcome weighting is the differentiator: plans that actually worked
        # count more (spec §13.1 "outcome is the secret ingredient"). Similarity
        # is squared so a close match dominates loosely-related neighbours.
        w = (n.score ** 2) * (0.5 + 0.5 * outcome)
        b = by_dx[dx]
        b["weight"] += w
        b["icd"] = p.get("icd", b["icd"])
        b["count"] += 1
        b["improved"].append(outcome)
        b["readmit"].append(1.0 if outcome < 0.5 else 0.0)
        if p.get("next_best_test"):
            b["tests"][p["next_best_test"]] += w
        # Keep the treatment from the highest-outcome neighbour of this dx.
        if not b["treatment"] or outcome >= max(b["improved"]):
            b["treatment"] = p.get("treatment", {}) or {}
        b["ids"].append(n.episode_id)

    weights = np.array([v["weight"] for v in by_dx.values()], dtype=np.float64)
    # Temperature-scaled normalization → calibrated probabilities.
    scaled = np.power(weights, 1.0 / _TEMPERATURE)
    probs = scaled / scaled.sum() if scaled.sum() > 0 else scaled

    out: list[Candidate] = []
    for (dx, v), prob in zip(by_dx.items(), probs):
        best_test = max(v["tests"], key=v["tests"].get) if v["tests"] else None
        out.append(
            Candidate(
                condition=dx,
                icd=v["icd"],
                probability=float(prob),
                raw_weight=float(v["weight"]),
                similar_cases=v["count"],
                outcomes={
                    "improved": round(float(np.mean(v["improved"])), 2),
                    "readmission_30d": round(float(np.mean(v["readmit"])), 2),
                },
                next_best_test=best_test,
                treatment=v["treatment"],
                supporting_episode_ids=v["ids"],
            )
        )

    out.sort(key=lambda c: c.probability, reverse=True)
    return out


def is_ood(neighbors: list[Neighbor], threshold: float = 0.18) -> bool:
    """Out-of-distribution check (spec §12.4): nothing in the KB looks similar."""
    if not neighbors:
        return True
    return neighbors[0].score < threshold


def band_for(probability: float) -> str:
    """Map a calibrated probability to a confidence band (spec §6.4)."""
    if probability >= 0.55:
        return "High"
    if probability >= 0.30:
        return "Moderate"
    return "Low"
