"""Zhipu GLM deep-analysis / RAG layer (spec §6 `reasoner.py`, §6.2, §12.5).

Optional, behind LLM_REASONING. Grounded and citation-required: the system
prompt forces every claim to cite a retrieved episode, forbids inventing
drugs/doses, and defers to the rules layer. Output is re-vetoed by rules/safety
downstream. On any failure it returns None and the deterministic pipeline stands
(degraded mode — reasoner offline). Never blocks the response indefinitely.
"""

from __future__ import annotations

import json

from app.ai.zhipu import get_zhipu_provider
from app.config import settings
from app.engine.classify import Candidate
from app.engine.vector_index import Neighbor
from app.observability.logging import get_logger
from app.observability.metrics import DEGRADED_MODE

log = get_logger("medisense.reasoner")

_SYSTEM = (
    "You are MediSense's clinical reasoning layer, assisting a licensed physician. "
    "You MUST ground every statement in one of the provided retrieved cases and cite it "
    "by its index like [case 2]. Never invent drugs, doses, or facts not supported by a "
    "retrieved case. Defer to the safety rules layer; never contradict a red flag. You do "
    "not make decisions — the physician confirms everything. Return ONLY a JSON object: "
    '{"summary": string, "refinements": [{"condition": string, "note": string, "cite": int}]}. '
    "Write summary in the requested language."
)


def _cases_block(neighbors: list[Neighbor], limit: int = 6) -> str:
    lines = []
    for i, n in enumerate(neighbors[:limit]):
        e = n.episode
        lines.append(
            f"[case {i}] dx={e.diagnosis} ({e.icd}); outcome={e.outcome:.2f}; "
            f"sim={n.similarity:.2f}; symptoms={e.symptom_text[:160]}"
        )
    return "\n".join(lines)


async def llm_reason(
    summary: str,
    candidates: list[Candidate],
    neighbors: list[Neighbor],
    lang: str,
) -> str | None:
    """Return a grounded, refined summary string, or None if unavailable.

    Only the natural-language summary is augmented; probabilities, rankings, and
    safety flags remain owned by the deterministic layers (cannot be overridden
    by generated text)."""
    if not settings.llm_configured:
        return None
    provider = get_zhipu_provider()
    if provider is None:
        DEGRADED_MODE.labels(component="reasoner").inc()
        return None

    user = (
        f"Language: {lang}\n"
        f"Deterministic summary: {summary}\n"
        f"Top differential: {[ (c.condition, round(c.probability,2)) for c in candidates[:4] ]}\n"
        f"Retrieved cases:\n{_cases_block(neighbors)}\n\n"
        "Refine the summary, citing cases. Do not change the ranking or invent treatments."
    )
    try:
        raw = await provider.reason(_SYSTEM, user, max_tokens=settings.llm_max_tokens)
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        log.warning("reasoner_failed", extra={"error": str(exc)})
        DEGRADED_MODE.labels(component="reasoner").inc()
        return None

    # Parse defensively; suppress anything not grounded/parseable (spec §12.6).
    try:
        s = raw[raw.index("{") : raw.rindex("}") + 1]
        obj = json.loads(s)
        refined = str(obj.get("summary", "")).strip()
        # Require a citation marker to accept generated content.
        if refined and "[case" in (raw):
            return refined
    except Exception:  # noqa: BLE001
        pass
    return None
