"""Chat surface — POST /api/clinical, GET /api/health (spec §4.1).

This is the contract the existing React UI consumes; shapes are honored exactly.
The endpoint is read-only (a suggestion, never a commit) so the current unauthed
frontend keeps working; an authenticated actor is recorded when a token is sent.
"""

from __future__ import annotations

import json
import re
import time

from fastapi import APIRouter

from app.config import settings
from app.db.seed import episode_count
from app.deps import OptionalUser, SessionDep
from app.engine import orchestrator
from app.engine.enrich import enrich, parse_allergies, parse_medications
from app.models import Suggestion
from app.observability.logging import get_logger
from app.observability.metrics import DIFFERENTIAL_LATENCY, SUGGESTIONS
from app.schemas import ClinicalRequest, ClinicalResponse, HealthResponse
from app.security.audit import record_event

router = APIRouter(tags=["chat"])
log = get_logger("medisense.clinical")

_DOCTOR_LINE = re.compile(r"^DOCTOR:\s*(.*)$", re.I | re.M)


@router.get("/api/health", response_model=HealthResponse)
async def health(session: SessionDep) -> HealthResponse:
    try:
        episodes = await episode_count(session)
    except Exception:  # noqa: BLE001 - health must never hard-fail
        episodes = 0
    return HealthResponse(
        ok=True,
        episodes=episodes,
        modelVersion=settings.model_version,
        ruleSetVersion=settings.ruleset_version,
        drugRefVersion=settings.drugref_version,
        llmReasoning=settings.llm_configured,
        datastore=settings.datastore_label,
    )


def _doctor_turns(req: ClinicalRequest) -> list[str]:
    if req.messages:
        return [m.text or "" for m in req.messages if (m.role or "").lower() == "doctor" and (m.text or "").strip()]
    if req.prompt:
        lines = _DOCTOR_LINE.findall(req.prompt)
        return [ln for ln in lines if ln.strip()] or [req.prompt.strip()]
    return []


def _case_text_and_intent(req: ClinicalRequest) -> tuple[str, str, str]:
    """Return (clinical case text, full text for safety parsing, last turn).

    A short, purely-prescriptive turn ("what should I prescribe?") is excluded
    from the clinical case so it does not pollute retrieval, but ALL turns are
    kept for allergy/medication parsing so the safety screen never loses data."""
    turns = _doctor_turns(req)
    full_text = "\n".join(turns)
    clinical_turns = [
        t for t in turns if not (orchestrator.is_prescriptive(t) and len(t.split()) < 8)
    ]
    case_text = "\n".join(clinical_turns) or full_text
    last = turns[-1] if turns else ""
    return case_text.strip(), full_text.strip(), last.strip()


@router.post("/api/clinical", response_model=ClinicalResponse)
async def clinical(req: ClinicalRequest, session: SessionDep, user: OptionalUser) -> ClinicalResponse:
    case_text, full_text, last_turn = _case_text_and_intent(req)
    lang = req.lang or "en"
    # Parse allergies/meds from ALL turns so the safety screen is complete, but
    # embed/diagnose only the clinical description.
    patient = enrich(
        case_text,
        {
            "lang": lang,
            "allergies": parse_allergies(full_text),
            "medications": parse_medications(full_text),
        },
    )

    start = time.perf_counter()
    outcome = await orchestrator.diagnose(session, patient)
    DIFFERENTIAL_LATENCY.observe(time.perf_counter() - start)

    treatment = None
    if outcome.candidates and orchestrator.is_prescriptive(last_turn):
        best = orchestrator.select_best_diagnosis(outcome)
        if best is not None:
            treatment = await orchestrator.build_treatment(session, best.condition, patient)

    reply = orchestrator.to_v1_reply(outcome, lang, treatment)
    SUGGESTIONS.labels(kind="differential", degraded=str(outcome.degraded_mode)).inc()

    # Persist the suggestion + audit the view (best-effort; never breaks the reply).
    try:
        actor = user.name if user else "anonymous"
        role = user.role if user else None
        suggestion = Suggestion(
            kind="treatment" if treatment else "differential",
            payload=reply,
            model_version=settings.model_version,
            ruleset_version=settings.ruleset_version,
            drugref_version=settings.drugref_version if treatment else None,
            degraded=outcome.degraded_mode,
        )
        session.add(suggestion)
        await session.flush()
        await record_event(
            session,
            actor=actor,
            role=role,
            action="suggestion.view",
            target=f"suggestion:{suggestion.id}",
            detail={
                "redFlag": bool(outcome.banner),
                "leading": reply["differential"][0]["condition"] if reply["differential"] else None,
                "degraded": outcome.degraded_mode,
                "ood": outcome.ood,
            },
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        log.warning("clinical_persist_failed", extra={"error": str(exc)})

    return ClinicalResponse(text=json.dumps(reply, ensure_ascii=False))
