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

from app.ai import chat_provider_name
from app.config import settings
from app.db.seed import episode_count
from app.deps import OptionalUser, SessionDep
from app.engine import conversation, demo_derm, orchestrator
from app.engine.enrich import enrich, parse_allergies, parse_medications
from app.models import Suggestion
from app.observability.logging import get_logger
from app.observability.metrics import DIFFERENTIAL_LATENCY, SUGGESTIONS
from app.schemas import ClinicalRequest, ClinicalResponse, HealthResponse
from app.security.audit import record_event

router = APIRouter(tags=["chat"])
log = get_logger("medisense.clinical")

_DOCTOR_LINE = re.compile(r"^DOCTOR:\s*(.*)$", re.I | re.M)

# A latest turn that reads as a question / clarification about the prior answer
# (rather than a fresh lesion description) is answered conversationally.
_FOLLOWUP_RE = re.compile(
    r"\b(why|how|what|which|when|who|is|are|was|were|can|could|should|would|will|do|"
    r"does|did|explain|tell|clarify|instead|versus|vs|safe|safety|dose|dosage|"
    r"pregnan|breastfeed|side\s*effect|alternative|contraindic|interact|monitor|"
    r"thanks|thank|hello|hi|hey|ok|okay)\b",
    re.I,
)

# Morphology cues that signal a *new lesion being described* (not a condition
# name — "why psoriasis vs eczema" names conditions but describes no new lesion).
_MORPHOLOGY = {
    "scale", "scales", "scaly", "plaque", "plaques", "papule", "papules", "pustule",
    "pustules", "vesicle", "vesicles", "bulla", "bullae", "macule", "patch", "patches",
    "nodule", "nodules", "ulcer", "ulcers", "wheal", "wheals", "crust", "crusts",
    "comedone", "comedones", "annular", "silvery", "pearly", "telangiectasia",
    "blister", "blisters", "erosion", "erosions", "lesion", "lesions", "mole",
    "nevus", "pigmented", "honey", "hyperkeratotic", "vesicular", "crusted",
}
_WORD_RE = re.compile(r"[a-z]+")


def _is_followup(last_turn: str) -> bool:
    """True when the latest turn is a follow-up question, not a new case.

    A fresh lesion description carries morphology cues (≥2 of scale/plaque/…);
    a comparison or clarification question ("why psoriasis over eczema?") names
    conditions but describes no new lesion, so it is answered conversationally.
    """
    t = (last_turn or "").strip()
    if not t:
        return False
    morphology = sum(1 for w in _WORD_RE.findall(t.lower()) if w in _MORPHOLOGY)
    if morphology >= 2:
        return False
    return t.endswith("?") or bool(_FOLLOWUP_RE.search(t))


def _chat_only_reply(text: str, base: dict) -> dict:
    """A pure conversational reply (renders as a chat bubble, no diagnosis card)."""
    return {
        "redFlag": "",
        "summary": text,
        "differential": [],
        "nextBestTest": "",
        "treatment": None,
        "modelVersion": base.get("modelVersion", settings.model_version),
        "ruleSetVersion": base.get("ruleSetVersion", settings.ruleset_version),
        "requiresPhysicianConfirmation": True,
        "degradedMode": False,
        "ood": False,
        "aiChat": True,
    }


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
        demoMode=settings.demo_mode and not settings.llm_configured,
        aiChat=settings.chat_configured,
        aiProvider=chat_provider_name(),
    )


def _doctor_turns(req: ClinicalRequest) -> list[str]:
    if req.messages:
        return [
            m.text or ""
            for m in req.messages
            if (m.role or "").lower() == "doctor" and (m.text or "").strip()
        ]
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
async def clinical(
    req: ClinicalRequest, session: SessionDep, user: OptionalUser
) -> ClinicalResponse:
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

    # Demo mode: when the LLM reasoner is offline, a clearly-dermatological case
    # is answered by the deterministic KB matcher (differential + first-line Rx).
    # Non-skin cases return None here and fall through to the general engine.
    reply = None
    if settings.demo_mode and not settings.llm_configured:
        reply = demo_derm.diagnose(case_text, lang)

    if reply is not None:
        DIFFERENTIAL_LATENCY.observe(time.perf_counter() - start)
        treatment = reply.get("treatment")
        outcome = None
        SUGGESTIONS.labels(kind="demo", degraded="False").inc()
    else:
        outcome = await orchestrator.diagnose(session, patient)
        DIFFERENTIAL_LATENCY.observe(time.perf_counter() - start)

        treatment = None
        if outcome.candidates and orchestrator.is_prescriptive(last_turn):
            best = orchestrator.select_best_diagnosis(outcome)
            if best is not None:
                treatment = await orchestrator.build_treatment(session, best.condition, patient)

        reply = orchestrator.to_v1_reply(outcome, lang, treatment)
        SUGGESTIONS.labels(kind="differential", degraded=str(outcome.degraded_mode)).inc()

    # Conversational language layer (optional). The grounded differential,
    # treatment, and safety flags are NEVER changed here — only the natural-
    # language narrative is upgraded, and genuine follow-up turns get a real
    # chat answer. Falls back silently to the templated text when no key is set.
    if settings.chat_configured:
        history_msgs = [
            {"role": m.role, "text": m.text or ""}
            for m in (req.messages or [])
            if (m.text or "").strip()
        ] or [{"role": "doctor", "text": case_text}]
        # A follow-up question answers conversationally (the freshly-computed
        # grounded reply is passed only as context, so doses/safety are accurate)
        # and renders as a chat bubble rather than re-showing the differential.
        followup = len(history_msgs) > 1 and _is_followup(last_turn)
        try:
            if followup:
                chatted = await conversation.chat_reply(history_msgs, reply, lang)
                if chatted:
                    reply = _chat_only_reply(chatted, reply)
            elif reply.get("differential"):
                narrated = await conversation.narrate(reply, lang)
                if narrated:
                    reply["summary"] = narrated
                    reply["aiChat"] = True
            else:
                chatted = await conversation.chat_reply(history_msgs, reply, lang)
                if chatted:
                    reply["summary"] = chatted
                    reply["aiChat"] = True
        except Exception as exc:  # noqa: BLE001 - conversation is best-effort
            log.warning("conversation_failed", extra={"error": str(exc)})

    # Persist the suggestion + audit the view (best-effort; never breaks the reply).
    degraded = bool(reply.get("degradedMode")) if outcome is None else outcome.degraded_mode
    try:
        actor = user.name if user else "anonymous"
        role = user.role if user else None
        suggestion = Suggestion(
            kind="treatment" if treatment else "differential",
            payload=reply,
            model_version=reply.get("modelVersion", settings.model_version),
            ruleset_version=settings.ruleset_version,
            drugref_version=settings.drugref_version if treatment else None,
            degraded=degraded,
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
                "redFlag": bool(reply.get("redFlag")),
                "leading": reply["differential"][0]["condition"] if reply["differential"] else None,
                "demo": outcome is None,
                "degraded": degraded,
                "ood": reply.get("ood", False) if outcome is None else outcome.ood,
            },
        )
        await session.commit()
    except Exception as exc:  # noqa: BLE001
        await session.rollback()
        log.warning("clinical_persist_failed", extra={"error": str(exc)})

    return ClinicalResponse(text=json.dumps(reply, ensure_ascii=False))
