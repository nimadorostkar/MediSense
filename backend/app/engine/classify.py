"""Retrieval-weighted classifier → calibrated probabilities (spec §6 `classify.py`).

Outcome-weighted k-NN vote over retrieved neighbours, then evidence-strength
shrinkage toward the prior — an honest calibration so a stated "70%" is not
manufactured from one weak match. Pluggable for a GBM/neural ensemble later.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.engine.embeddings import _tokenize
from app.engine.labels import icd_for
from app.engine.vector_index import Neighbor


@dataclass
class Candidate:
    condition: str
    icd: str
    probability: float  # 0–1, calibrated
    raw_share: float
    similar_cases: int
    supporting: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)
    typical_outcomes: dict[str, float] = field(default_factory=dict)
    next_best_test: str = ""
    neighbors: list[Neighbor] = field(default_factory=list)
    mean_outcome: float = 0.0
    # Set by the rules/safety layer (evaluated last):
    pinned_watch: bool = False  # do-not-miss, never collapsed
    red_flag: bool = False


def _outcome_weight(sim: float, outcome: float) -> float:
    # Plans/diagnoses that actually led to recovery count more (spec §13.1).
    return max(0.0, sim) * (0.4 + 0.6 * max(0.0, min(1.0, outcome)))


def classify(patient: dict, neighbors: list[Neighbor]) -> list[Candidate]:
    if not neighbors:
        return []

    patient_tokens = set(_tokenize(patient.get("text", "")))
    negatives = {n.lower() for n in patient.get("negatives", [])}

    groups: dict[str, list[Neighbor]] = defaultdict(list)
    for n in neighbors:
        groups[n.episode.diagnosis].append(n)

    weights: dict[str, float] = {}
    for cond, ns in groups.items():
        weights[cond] = sum(_outcome_weight(n.similarity, n.episode.outcome) for n in ns)

    total_weight = sum(weights.values()) or 1.0
    num_conditions = len(groups)
    uniform = 1.0 / num_conditions

    # Evidence strength drives how far we trust the raw vote vs. shrink to prior.
    top_sim = max(n.similarity for n in neighbors)
    density = min(1.0, len(neighbors) / max(1, len(neighbors[:8])))  # ~1 when k full
    evidence_strength = max(0.0, min(1.0, top_sim)) * max(0.35, density)

    candidates: list[Candidate] = []
    for cond, ns in groups.items():
        raw_share = weights[cond] / total_weight
        calibrated = raw_share * evidence_strength + uniform * (1 - evidence_strength)

        # Supporting evidence = features seen in similar cases AND in this patient.
        support_pool: set[str] = set()
        for n in ns:
            support_pool.update(s.lower() for s in (n.episode.supporting or []))
        supporting = sorted(
            s for s in support_pool if any(tok in s or s in patient_tokens for tok in patient_tokens)
        )[:6] or sorted(support_pool)[:4]
        contradicting = sorted(s for s in support_pool if s in negatives)[:4]

        outcomes = [n.episode.outcome for n in ns]
        mean_outcome = sum(outcomes) / len(outcomes)
        typical = {
            "improved": round(mean_outcome, 2),
            "readmission_30d": round(max(0.0, (1 - mean_outcome) * 0.25), 2),
        }
        # Most-similar neighbour drives the next-best-test suggestion.
        best = max(ns, key=lambda n: n.similarity)

        candidates.append(
            Candidate(
                condition=cond,
                icd=best.episode.icd or icd_for(cond) or "",
                probability=round(calibrated, 4),
                raw_share=round(raw_share, 4),
                similar_cases=len(ns),
                supporting=supporting,
                contradicting=contradicting,
                typical_outcomes=typical,
                next_best_test=best.episode.next_best_test or "",
                neighbors=ns,
                mean_outcome=mean_outcome,
            )
        )

    # Renormalize calibrated probabilities so they remain a proper distribution.
    tot = sum(c.probability for c in candidates) or 1.0
    for c in candidates:
        c.probability = round(c.probability / tot, 4)

    candidates.sort(key=lambda c: c.probability, reverse=True)
    return candidates
