"""Conversational language layer (Gemini/Zhipu) over the grounded engine.

Two entry points, both optional and fail-safe (return None → the deterministic
templated text stands):

- ``narrate`` rewrites the *summary* of a diagnostic reply as a warm, natural,
  physician-facing explanation — grounded strictly in the differential, workup,
  and treatment the deterministic engine already computed. It may not add,
  remove, or re-rank diagnoses, drugs, or doses; those stay owned by the KB and
  safety layers and are rendered from the structured data untouched.
- ``chat_reply`` answers a genuine conversational turn (a follow-up like "why is
  it ranked first?", a clarification, a greeting) using the conversation history
  and the last grounded suggestion as context, so the assistant feels like a
  real chat while never inventing new clinical facts.
"""

from __future__ import annotations

from app.ai import get_chat_provider
from app.config import settings
from app.observability.logging import get_logger

log = get_logger("medisense.conversation")

_LANG_NAME = {"en": "English", "zh": "Simplified Chinese"}

_NARRATE_SYSTEM = (
    "You are MediSense, an AI clinical decision-support assistant talking to a licensed "
    "physician. You are given the structured result the deterministic engine already "
    "produced for a case. Write a brief, natural, collegial explanation of it in {lang} "
    "(2-4 sentences, no lists, no JSON, no markdown headings). Rules: use ONLY the facts "
    "provided — never introduce a diagnosis, drug, dose, or test that is not in the data, "
    "and never change the ranking or probabilities. Lead with the top consideration and "
    "why, mention the key next step, and if a red flag is present state it first. Always "
    "keep it as a suggestion the physician confirms; never sound certain or directive."
)

_CHAT_SYSTEM = (
    "You are MediSense, an AI clinical decision-support assistant for licensed physicians, "
    "specialised in dermatology. Reply conversationally in {lang} (concise, warm, "
    "professional; no markdown headings or JSON). You may explain or clarify the previous "
    "suggestion shown below, discuss general clinical reasoning, or answer follow-up "
    "questions. Do NOT invent specific drugs, doses, or a new diagnosis that was not in the "
    "prior suggestion — if the physician is describing a new patient and wants a differential, "
    "briefly ask them to state the lesion morphology, distribution, and duration. Always "
    "assist rather than replace; the physician confirms every decision. Keep replies short."
)


def _lang(lang: str) -> str:
    return _LANG_NAME.get(lang, "English")


def _facts(reply: dict) -> str:
    """Render the grounded structured reply into a compact fact sheet for the LLM."""
    lines: list[str] = []
    if reply.get("redFlag"):
        lines.append(f"RED FLAG: {reply['redFlag']}")
    diff = reply.get("differential") or []
    if diff:
        lines.append("Differential (fixed ranking):")
        for d in diff:
            lines.append(
                f"  - {d['condition']} ({d.get('icd','')}) {d['probability']}% "
                f"[{d['confidence']}] — {d.get('because','')}"
            )
    if reply.get("nextBestTest"):
        lines.append(f"Next best test: {reply['nextBestTest']}")
    tx = reply.get("treatment")
    if tx:
        lines.append(f"Suggested first-line for {tx.get('bestDiagnosis','')}:")
        for m in tx.get("medications", [])[:5]:
            lines.append(
                f"  - {m.get('drug','')} {m.get('dose','')} {m.get('duration','')}".rstrip()
            )
        for f in tx.get("safety", []):
            lines.append(f"  SAFETY [{f.get('severity','')}]: {f.get('message','')}")
        if tx.get("monitoring"):
            lines.append(f"  Monitoring: {tx['monitoring']}")
    return "\n".join(lines) if lines else "No specific findings were matched."


async def narrate(reply: dict, lang: str) -> str | None:
    """Return a natural-language summary grounded in `reply`, or None."""
    if not settings.chat_configured:
        return None
    provider = get_chat_provider()
    if provider is None:
        return None
    system = _NARRATE_SYSTEM.format(lang=_lang(lang))
    user = (
        "Structured engine result:\n"
        f"{_facts(reply)}\n\n"
        "Write the physician-facing explanation now."
    )
    try:
        text = await provider.reason(system, user, max_tokens=min(settings.llm_max_tokens, 400))
    except Exception as exc:  # noqa: BLE001 - degrade to templated text
        log.warning("narrate_failed", extra={"error": str(exc)})
        return None
    text = (text or "").strip()
    return text or None


async def chat_reply(messages: list[dict], last_reply: dict | None, lang: str) -> str | None:
    """Return a conversational answer for a non-diagnostic turn, or None.

    `messages` is the doctor/ai turn history [{role, text}]; `last_reply` is the
    most recent grounded suggestion (for context)."""
    if not settings.chat_configured:
        return None
    provider = get_chat_provider()
    if provider is None:
        return None

    context = _facts(last_reply) if last_reply else "None yet."
    system = _CHAT_SYSTEM.format(lang=_lang(lang)) + f"\n\nPrevious suggestion for context:\n{context}"
    try:
        if hasattr(provider, "chat"):
            text = await provider.chat(messages, system=system, max_tokens=480, temperature=0.6)
        else:
            transcript = "\n".join(
                f"{'Doctor' if (m.get('role') or '').lower() in ('doctor','user') else 'MediSense'}: "
                f"{(m.get('text') or '').strip()}"
                for m in messages
                if (m.get("text") or "").strip()
            )
            text = await provider.reason(
                system, transcript + "\n\nMediSense:", max_tokens=480
            )
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        log.warning("chat_reply_failed", extra={"error": str(exc)})
        return None
    text = (text or "").strip()
    return text or None
