"""Conversational language layer (Gemini/Zhipu) — normal conversation ONLY.

The AI is deliberately confined to *chatting*. It never recognises a condition,
never writes or rewrites a differential, dose, or safety flag, and never
narrates a clinical answer — those are produced entirely by the deterministic
engine from the KB data files. This module has a single entry point:

- ``chat_reply`` answers a genuine conversational turn (a follow-up like "why is
  it ranked first?", a clarification, a greeting) using the conversation history
  and the last grounded suggestion as read-only context, so the assistant feels
  like a real chat while never inventing or altering any clinical fact.

Both are optional and fail-safe (return None → the deterministic templated text
stands), so the product works identically with the AI layer switched off.
"""

from __future__ import annotations

from app.ai import get_chat_provider
from app.config import settings
from app.observability.logging import get_logger

log = get_logger("medisense.conversation")

_LANG_NAME = {"en": "English", "zh": "Simplified Chinese"}

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
