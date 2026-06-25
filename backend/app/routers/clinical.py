"""Chat-compatible endpoint consumed by the React chat UI.

POST /api/clinical  { messages: [{role, text}], lang }  (also accepts legacy
{prompt, lang}) → { text: "<DiagnosisReply JSON string>" }.

The engine — not an LLM — produces the ranked differential and the screened
treatment. The reply is the structured object the UI's parseReply() expects.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from .. import audit_util
from ..db import get_session
from ..engine import orchestrator
from ..models import Encounter, Suggestion
from ..schemas import ClinicalResponse
from ..versions import MODEL_VERSION, RULESET_VERSION

router = APIRouter()


def _messages_from_body(body: dict) -> tuple[list[dict], str]:
    lang = body.get("lang", "en")
    if isinstance(body.get("messages"), list) and body["messages"]:
        msgs = [
            {"role": "doctor" if m.get("role") in ("doctor", "user") else "ai",
             "text": m.get("text", "")}
            for m in body["messages"]
        ]
        return msgs, lang
    # Legacy: a single prompt string becomes one doctor turn.
    return [{"role": "doctor", "text": body.get("prompt", "")}], lang


@router.post("/api/clinical", response_model=ClinicalResponse)
async def clinical(request: Request, session: AsyncSession = Depends(get_session)) -> ClinicalResponse:
    body = await request.json()
    messages, lang = _messages_from_body(body)

    reply = await orchestrator.run_chat(messages, lang)

    # Persist the encounter + suggestion + audit (best-effort; never blocks UX).
    try:
        case_text, _ = orchestrator.extract_case(messages)
        enc = Encounter(symptom_text=case_text, lang=lang)
        session.add(enc)
        await session.flush()
        session.add(Suggestion(
            encounter_id=enc.id, kind="differential", payload=reply,
            model_version=MODEL_VERSION, ruleset_version=RULESET_VERSION,
        ))
        await audit_util.record(session, actor="chat", action="differential_generated",
                                target=enc.id, detail={"conditions": [d["condition"] for d in reply["differential"]]})
        await session.commit()
    except Exception:
        await session.rollback()

    return ClinicalResponse(text=json.dumps(reply, ensure_ascii=False))
