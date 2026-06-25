"""Pipeline orchestrator (spec §12.2).

Order is the safety contract: retrieve → classify → calibrate → RULES LAST.
Produces the chat-UI DiagnosisReply and the /v2 differential. The rules/safety
layer can always override; every output carries version stamps and
requiresPhysicianConfirmation.
"""
from __future__ import annotations

from .embeddings import get_embedder
from .vector_index import get_index
from . import classify as clf
from . import rules as rules_mod
from . import recommend
from .labels import localize
from .reasoning import differential_summary, polish
from ..versions import MODEL_VERSION, RULESET_VERSION

_RX_KEYWORDS = (
    "prescrib", "medication", "medicine", "drug", "antibiotic", "treat",
    "treatment", "therapy", "dose", "dosing", "rx", "manage", "what is safe",
    "what should i give", "best diagnosis", "plan", "solution",
    "处方", "用药", "药物", "治疗", "方案", "抗生素", "剂量",
)
_MAX_DIFF = 4


def detect_intent(latest_text: str) -> str:
    t = (latest_text or "").lower()
    return "treatment" if any(k in t for k in _RX_KEYWORDS) else "differential"


def extract_case(messages: list[dict]) -> tuple[str, str]:
    """Join doctor turns into the case text; return (case_text, latest_text)."""
    doctor = [m.get("text", "") for m in messages if m.get("role") == "doctor"]
    case_text = "  ".join(t for t in doctor if t).strip()
    latest = doctor[-1] if doctor else case_text
    return case_text, latest


def _diff_candidates(case_text: str):
    """Core engine pass shared by differential + treatment."""
    embedder = get_embedder()
    index = get_index()
    q = embedder.embed(case_text)
    neighbors = index.search(q, k=6)
    candidates = clf.classify(neighbors)
    ood = clf.is_ood(neighbors)
    rule_hit = rules_mod.evaluate(case_text)
    return candidates, ood, rule_hit


def _build_differential(candidates, rule_hit, ood, lang="en"):
    """Assemble UI differential rows, pinning do-not-miss conditions as Watch."""
    items = []
    present = set()
    for c in candidates[:_MAX_DIFF]:
        prob = c.probability * (0.85 if ood else 1.0)
        items.append({
            "condition": localize(c.condition, lang),
            "icd": c.icd,
            "probability": round(prob * 100, 1),
            "confidence": clf.band_for(prob),
            "because": _because(c, lang),
        })
        present.add(c.condition.lower())

    # Anti-anchoring: pin do-not-miss conditions the classifier may have missed.
    for dnm in rule_hit.do_not_miss:
        if dnm["condition"].lower() not in present:
            items.append({
                "condition": localize(dnm["condition"], lang),
                "icd": dnm.get("icd", ""),
                "probability": 8.0,
                "confidence": "Watch",
                "because": dnm["because"],
            })
    return items


def _because(c, lang="en") -> str:
    out = round(c.outcomes.get("improved", 0) * 100)
    if lang == "zh":
        return f"{c.similar_cases} 个相似病例；匹配方案约 {out}% 改善"
    return f"{c.similar_cases} similar case(s); ~{out}% improved on the matched plan"


async def run_chat(messages: list[dict], lang: str = "en") -> dict:
    case_text, latest = extract_case(messages)
    intent = detect_intent(latest)
    candidates, ood, rule_hit = _diff_candidates(case_text)

    # Non-clinical / empty case → summary only (frontend shows it as prose).
    if not candidates and not rule_hit.red_flag:
        msg = ("请描述患者的症状、年龄、病史和生命体征，我将给出鉴别诊断。"
               if lang == "zh"
               else "Describe the patient's symptoms, age, history and vitals and I'll return a ranked differential.")
        return _reply(summary=msg)

    differential = _build_differential(candidates, rule_hit, ood, lang)
    top = candidates[0] if candidates else None
    summary = await polish(differential_summary(top, ood, lang), lang)
    next_best = (top.next_best_test if top and top.next_best_test else "")

    reply = _reply(
        red_flag=rule_hit.red_flag or "",
        summary=summary,
        differential=differential,
        next_best_test=next_best or "",
    )

    # Treatment step: when the doctor asks to treat/prescribe, attach the plan
    # for the chosen (or top) diagnosis — the "best diagnosis + solution" step.
    if intent == "treatment" and top:
        chosen = _match_condition(latest, candidates) or top
        allergies, meds = _patient_safety_context(messages)
        reply["treatment"] = recommend.build_treatment(
            condition=chosen.condition, icd=chosen.icd,
            treatment_dict=chosen.treatment, outcomes=chosen.outcomes,
            allergies=allergies, current_meds=meds, lang=lang,
        )
    return reply


def _match_condition(text: str, candidates):
    t = (text or "").lower()
    for c in candidates:
        if c.condition.lower() in t:
            return c
    return None


def _patient_safety_context(messages: list[dict]) -> tuple[list[str], list[str]]:
    """Best-effort extraction of allergies / current meds from the chat text."""
    blob = " ".join(m.get("text", "") for m in messages if m.get("role") == "doctor").lower()
    allergies, meds = [], []
    for known in ("penicillin", "sulfa", "aspirin", "nsaid", "codeine"):
        if f"{known} allerg" in blob or f"allergic to {known}" in blob:
            allergies.append(known)
    for drug in ("warfarin", "metformin", "aspirin", "lisinopril", "amoxicillin",
                 "ibuprofen", "atorvastatin", "clarithromycin"):
        if drug in blob:
            meds.append(drug)
    return allergies, meds


def _reply(red_flag="", summary="", differential=None, next_best_test="") -> dict:
    return {
        "redFlag": red_flag,
        "summary": summary,
        "differential": differential or [],
        "nextBestTest": next_best_test,
        "treatment": None,
        "modelVersion": MODEL_VERSION,
        "ruleSetVersion": RULESET_VERSION,
        "requiresPhysicianConfirmation": True,
    }
