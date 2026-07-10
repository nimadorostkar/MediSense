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
from app.engine import conversation, demo_derm, kb_answer, orchestrator
from app.engine.enrich import enrich, parse_allergies, parse_medications
from app.models import Suggestion
from app.observability.logging import get_logger
from app.observability.metrics import DIFFERENTIAL_LATENCY, SUGGESTIONS
from app.schemas import (
    ClinicalRequest,
    ClinicalResponse,
    HealthResponse,
    QuickLookRequest,
    QuickLookResponse,
)
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

# Chinese question / follow-up markers (the English regex can't see them).
_FOLLOWUP_ZH = ("为什么", "为何", "吗", "呢", "什么", "如何", "怎么", "多少", "哪",
                "谢谢", "你好", "您好", "再见")

# Small talk — the ONLY turns ever handed to the AI, and even then the AI is
# instructed to speak strictly from file-derived context. A turn qualifies only
# when it is PURE social conversation: it contains no question of any kind, at
# least one core greeting/thanks word, and nothing beyond the closed word lists
# below. "ok doc, you sure?" or "你好，会传染吗？" are clinical questions, not
# small talk — they are answered from the uploaded files (or told the answer is
# not in them), never by the AI.
_SMALLTALK_CORE = frozenset({
    "hi", "hello", "hey", "thanks", "thank", "bye", "goodbye", "morning",
    "afternoon", "evening", "ok", "okay", "great", "cool", "nice", "perfect",
    "awesome", "appreciate", "appreciated", "welcome", "helpful",
})
_SMALLTALK_FILLER = frozenset({
    "you", "good", "please", "much", "so", "very", "doc", "doctor", "a",
    "lot", "all", "that", "was", "got", "it",
})
_SMALLTALK_WORDS = _SMALLTALK_CORE | _SMALLTALK_FILLER
_SMALLTALK_ZH = ("你好", "您好", "谢谢", "多谢", "感谢", "再见", "好的", "哈喽", "早上好",
                 "下午好", "晚上好", "辛苦了")
_ZH_PUNCT_RE = re.compile(r"[\s，。！!,.；;、…~～]+")

_NOT_IN_FILES = {
    "en": "That information is not in the uploaded files, so I can't answer it here. "
    "I answer strictly from the uploaded knowledge files — you can ask about the "
    "conditions, treatments, doses, safety alerts, tests, or follow-up they contain.",
    "zh": "上传的资料文件中没有这一信息，因此无法在此作答。我只依据已上传的资料文件回答——"
    "您可以询问其中包含的疾病、治疗、剂量、安全警示、检查或随访内容。",
}

_GREETING = {
    "en": "Hello! Describe the case — lesion morphology, distribution, and duration — "
    "and I'll match it against the uploaded knowledge files.",
    "zh": "您好！请描述病例（皮损形态、分布、病程），我将依据已上传的资料文件进行匹配。",
}


def _is_smalltalk(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    # A question is never small talk, whatever else the turn contains.
    if any(q in t for q in ("?", "？", "吗", "呢")):
        return False
    if any(p in t for p in _SMALLTALK_ZH):
        # Chinese: the WHOLE turn must be consumed by greeting/thanks phrases
        # and punctuation. Any residue ("你好，会传染…") is a real question that
        # must be answered from the files, so it is not small talk.
        rest = t
        for p in _SMALLTALK_ZH:
            rest = rest.replace(p, "")
        return not _ZH_PUNCT_RE.sub("", rest).strip()
    words = re.findall(r"[a-z']+", t.lower())
    return (
        bool(words)
        and len(words) <= 8
        and all(w in _SMALLTALK_WORDS for w in words)
        and any(w in _SMALLTALK_CORE for w in words)
    )


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
    return (
        t.endswith("?")
        or t.endswith("？")
        or bool(_FOLLOWUP_RE.search(t))
        or any(z in t for z in _FOLLOWUP_ZH)
    )


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


@router.post("/api/quicklook", response_model=QuickLookResponse)
async def quicklook(req: QuickLookRequest) -> QuickLookResponse:
    """Live, file-grounded reading of the case as it is typed.

    Pure and deterministic: it matches the partial text against the uploaded
    dermatology files and returns recognised keywords + candidate conditions.
    It never calls an AI model, never persists, and never prescribes — it is a
    reading aid, not a decision. The full answer is produced only on submit via
    ``/api/clinical``."""
    try:
        result = demo_derm.preview((req.text or "").strip(), req.lang or "en")
    except Exception as exc:  # noqa: BLE001 - preview must never break typing
        log.warning("quicklook_failed", extra={"error": str(exc)})
        result = {"keywords": [], "diagnoses": []}
    return QuickLookResponse(
        keywords=result.get("keywords", []),
        diagnoses=result.get("diagnoses", []),
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

    # A clearly-dermatological case is answered by the deterministic KB matcher
    # over the uploaded dermatology files (differential + first-line Rx). No
    # configuration can divert it to a model (`llm_configured` is pinned False).
    # Non-skin cases return None here and fall through to the general engine.
    reply = None
    if settings.demo_mode and not settings.llm_configured:
        reply = demo_derm.diagnose(case_text, lang)

    # True when the dermatology KB matcher answered this turn — its output is a
    # clinical answer and must stand exactly as the KB produced it (never AI).
    used_kb_derm = reply is not None
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

    # ── File-grounded follow-up routing ──────────────────────────────────────
    # EVERY answer is created from the uploaded data files, never by an AI:
    #   • A described clinical case is answered verbatim by the deterministic
    #     engine over the uploaded files (dermatology KB / episode file) above.
    #   • An informational follow-up ("what dose?", "why X vs Y?", "safe in
    #     pregnancy?") is answered by kb_answer — deterministic retrieval over
    #     the same uploaded files. If the files don't contain the answer, we say
    #     exactly that instead of letting a model guess.
    #   • The AI (Gemini/Zhipu) is consulted ONLY for small talk (greeting,
    #     thanks, goodbye) and is instructed to speak strictly from
    #     file-derived context — it never recognises or creates an answer.
    history_msgs = [
        {"role": m.role, "text": m.text or ""}
        for m in (req.messages or [])
        if (m.text or "").strip()
    ] or [{"role": "doctor", "text": case_text}]
    # ``_is_followup`` is False when ≥2 morphology cues are present, so a newly
    # described case is never diverted away from its diagnosis card.
    followup = _is_followup(last_turn) and (len(history_msgs) > 1 or not used_kb_derm)
    if followup and reply.get("treatment") and orchestrator.is_prescriptive(last_turn):
        # A prescriptive follow-up already carries the full treatment card built
        # from the files, including its safety flags — the card always beats a
        # prose rendering of the same data (which would drop the flags).
        pass
    elif followup:
        lang_key = "zh" if lang == "zh" else "en"
        grounded = None
        try:
            grounded = kb_answer.answer(last_turn, reply, lang)
        except Exception as exc:  # noqa: BLE001 - fall through to "not in files"
            log.warning("kb_answer_failed", extra={"error": str(exc)})
        if grounded:
            reply = _chat_only_reply(grounded, reply)
        elif _is_smalltalk(last_turn):
            chatted = None
            if settings.chat_configured:
                try:
                    # The grounded reply is passed only as read-only context; the
                    # AI is prompted to never add facts beyond that context.
                    chatted = await conversation.chat_reply(history_msgs, reply, lang)
                except Exception as exc:  # noqa: BLE001 - conversation is best-effort
                    log.warning("conversation_failed", extra={"error": str(exc)})
            reply = _chat_only_reply(chatted or _GREETING[lang_key], reply)
        elif used_kb_derm:
            # The dermatology KB already answered this turn from the files —
            # its card (or its own clarification ask) stands untouched.
            pass
        elif reply.get("differential") and not reply.get("ood"):
            # The general engine produced a differential grounded in the
            # uploaded episode file with adequate similarity — it stands.
            pass
        else:
            reply = _chat_only_reply(_NOT_IN_FILES[lang_key], reply)

    # Persist the suggestion + audit the view (best-effort; never breaks the reply).
    # `kind`/versions describe the FINAL reply — a follow-up turn may have
    # replaced the treatment card computed above with a chat bubble.
    persisted_treatment = reply.get("treatment")
    degraded = bool(reply.get("degradedMode")) if outcome is None else outcome.degraded_mode
    try:
        actor = user.name if user else "anonymous"
        role = user.role if user else None
        suggestion = Suggestion(
            kind="treatment" if persisted_treatment else "differential",
            payload=reply,
            model_version=reply.get("modelVersion", settings.model_version),
            ruleset_version=settings.ruleset_version,
            drugref_version=settings.drugref_version if persisted_treatment else None,
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
