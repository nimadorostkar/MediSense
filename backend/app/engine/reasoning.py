"""Reasoning / narrative layer.

Turns the engine's structured findings into the short clinician-facing prose the
chat UI shows (summary, rationale). Deterministic by default so the slice runs
offline; if ANTHROPIC_API_KEY is set, the text is polished by the model — but the
*rankings and safety flags always come from the engine*, never the LLM. This is
the grounded, rules-vetoed reasoning seam described in spec §12.5.
"""
from __future__ import annotations

import httpx

from ..config import get_settings
from .labels import localize

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def differential_summary(top, ood: bool, lang: str) -> str:
    if not top:
        return ("未找到足够相似的既往病例，请补充更多症状细节。" if lang == "zh"
                else "Not enough similar past cases were found — please add more symptom detail.")
    name = localize(top.condition, lang)
    pct = round(top.probability * 100)
    if lang == "zh":
        base = f"基于 {top.similar_cases} 个相似既往病例，最可能的是「{name}」（约 {pct}%）。"
        if ood:
            base += "（注意：该病例与知识库差异较大，置信度下调，请谨慎参考。）"
        return base
    base = (f"Based on {top.similar_cases} similar past case(s), the leading consideration is "
            f"{name} (~{pct}%).")
    if ood:
        base += " Note: this presentation is dissimilar to the knowledge base, so confidence is lowered — interpret with caution."
    return base


def treatment_rationale(condition: str, outcomes: dict, lang: str) -> str:
    condition = localize(condition, lang)
    improved = round(outcomes.get("improved", 0) * 100)
    if lang == "zh":
        return f"该方案来自确诊为「{condition}」且恢复良好的既往病例（约 {improved}% 改善），并已通过用药安全筛查。"
    return (f"This plan is drawn from past cases confirmed as {condition} with good recovery "
            f"(~{improved}% improved) and has passed the drug-safety screen.")


async def polish(text: str, lang: str) -> str:
    """Optional LLM polish of a narrative string. Falls back to the input."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return text
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                _ANTHROPIC_URL,
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.anthropic_model,
                    "max_tokens": 300,
                    "messages": [{
                        "role": "user",
                        "content": (
                            "Rewrite this clinical decision-support note more fluently for a "
                            f"physician in {'Simplified Chinese' if lang == 'zh' else 'English'}. "
                            "Keep it factual, do not add new clinical claims, one short paragraph:\n\n"
                            + text
                        ),
                    }],
                },
            )
            if r.status_code == 200:
                blocks = r.json().get("content", [])
                out = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                return out.strip() or text
    except Exception:
        pass
    return text
