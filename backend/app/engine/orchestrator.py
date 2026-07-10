"""Pipeline orchestrator (spec §6 `orchestrator.py`, §6.1).

Runs the safety contract in order and never reorders it:

    enrich → retrieve → classify → calibrate → apply_rules (LAST) → rank/explain
    ;  treatment: recommend → safety_screen (hard veto)

Every stage is deterministic over the uploaded data files — the former optional
LLM summary-refinement step is retired so no model-generated text can ever
appear in a clinical answer. Stamps every output with model/rule/drugref
versions and `requiresPhysicianConfirmation`. Degrades gracefully: a downed
classifier yields a labelled, reduced answer — never a blank screen, and hard
safety blocks still hold (spec §7).
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.engine import drug_safety
from app.engine.classify import Candidate, classify
from app.engine.embeddings import embed_text
from app.engine.labels import condition_label, drug_label, icd_for, test_label
from app.engine.ood import detect_ood
from app.engine.recommend import recommend_treatment
from app.engine.rules import apply_rules
from app.engine.vector_index import Neighbor, retrieve
from app.schemas import Band

_PRESCRIBE_RE = re.compile(
    r"\b(prescrib|treat|treatment|medicat|drug|rx|manage|management|therapy|give|antibiotic)\w*",
    re.I,
)
_PRESCRIBE_ZH = ("处方", "治疗", "用药", "开药", "药物")
_MIN_TOKENS = 3


@dataclass
class DifferentialOutcome:
    candidates: list[Candidate]
    red_flags: list[str] = field(default_factory=list)
    banner: str = ""
    ood: bool = False
    ood_reason: str = ""
    degraded_mode: bool = False
    degraded_components: list[str] = field(default_factory=list)
    neighbors: list[Neighbor] = field(default_factory=list)


def is_prescriptive(text: str) -> bool:
    return bool(_PRESCRIBE_RE.search(text)) or any(z in text for z in _PRESCRIBE_ZH)


def band_for(probability: float, pinned_watch: bool) -> Band:
    if pinned_watch:
        return "Watch"
    if probability >= 0.70:
        return "High"
    if probability >= 0.40:
        return "Moderate"
    return "Low"


def _retrieval_only_candidates(neighbors: list[Neighbor]) -> list[Candidate]:
    """Degraded path: differential from retrieval alone (classifier offline)."""
    groups: dict[str, list[Neighbor]] = defaultdict(list)
    for n in neighbors:
        groups[n.episode.diagnosis].append(n)
    total = sum(max(0.0, n.similarity) for n in neighbors) or 1.0
    cands = []
    for cond, ns in groups.items():
        share = sum(max(0.0, n.similarity) for n in ns) / total
        best = max(ns, key=lambda n: n.similarity)
        outcomes = [n.episode.outcome for n in ns]
        cands.append(
            Candidate(
                condition=cond,
                icd=best.episode.icd or icd_for(cond) or "",
                probability=round(share, 4),
                raw_share=round(share, 4),
                similar_cases=len(ns),
                condition_zh=best.episode.diagnosis_zh or "",
                supporting=[s.lower() for s in (best.episode.supporting or [])][:5],
                typical_outcomes={"improved": round(sum(outcomes) / len(outcomes), 2)},
                next_best_test=best.episode.next_best_test or "",
                next_best_test_zh=best.episode.next_best_test_zh or "",
                neighbors=ns,
                mean_outcome=sum(outcomes) / len(outcomes),
            )
        )
    cands.sort(key=lambda c: c.probability, reverse=True)
    return cands


async def diagnose(
    session: AsyncSession,
    patient: dict,
    *,
    classifier_online: bool = True,
) -> DifferentialOutcome:
    text = patient.get("text", "").strip()
    if len(text.split()) < _MIN_TOKENS:
        return DifferentialOutcome(candidates=[], banner="", degraded_mode=False)

    # retrieve
    query_vec = await embed_text(text)
    neighbors = await retrieve(session, query_vec)

    degraded_components: list[str] = []

    # classify → calibrate (or degraded retrieval-only)
    if classifier_online:
        candidates = classify(patient, neighbors)
    else:
        candidates = _retrieval_only_candidates(neighbors)
        degraded_components.append("classifier")

    # apply_rules — LAST, hard veto / do-not-miss surfacing
    rules_result = apply_rules(candidates, patient)

    # ood
    ood_result = detect_ood(neighbors)

    # The former optional LLM summary refinement is retired: the summary is
    # always the deterministic text derived from the uploaded files.
    return DifferentialOutcome(
        candidates=rules_result.candidates,
        red_flags=rules_result.red_flags,
        banner=rules_result.banner,
        ood=ood_result.is_ood,
        ood_reason=ood_result.reason,
        degraded_mode=bool(degraded_components),
        degraded_components=degraded_components,
        neighbors=neighbors,
    )


def _summary_text(outcome: DifferentialOutcome, lang: str) -> str:
    if not outcome.candidates:
        return (
            "请提供症状描述以生成鉴别诊断。"
            if lang == "zh"
            else "Please provide a symptom description to generate a differential."
        )
    # Leading consideration = the top *statistical* candidate backed by cases
    # (do-not-miss items are surfaced via the banner, not as the "leading" line).
    backed = [c for c in outcome.candidates if c.similar_cases > 0]
    lead = max(backed or outcome.candidates, key=lambda c: c.probability)
    label = condition_label(lead.condition, lang, lead.condition_zh)
    pct = round(lead.probability * 100, 1)
    base = (
        f"基于 {lead.similar_cases} 个相似既往病例，首要考虑为 {label}（约{pct}%）。"
        if lang == "zh"
        else f"Based on {lead.similar_cases} similar past case(s), the leading consideration is "
        f"{label} (~{pct:g}%)."
    )
    if outcome.ood:
        base += (
            " 该患者与知识库差异较大——置信度低，建议升级会诊。"
            if lang == "zh"
            else " This patient is unusual — low confidence, consider escalation."
        )
    if "classifier" in outcome.degraded_components:
        base += (
            " (degraded mode — classifier offline)" if lang != "zh" else "（降级模式——分类器离线）"
        )
    return base


def _because(c: Candidate, lang: str) -> str:
    if c.pinned_watch and c.similar_cases == 0:
        return (
            "不可漏诊——尽管概率低仍予提示。"
            if lang == "zh"
            else "do-not-miss — surfaced despite low probability"
        )
    improved = c.typical_outcomes.get("improved")
    if lang == "zh":
        s = f"{c.similar_cases} 个相似病例"
        if improved is not None:
            s += f"；约{round(improved*100)}%在匹配方案下改善"
        return s
    s = f"{c.similar_cases} similar case(s)"
    if improved is not None:
        s += f"; ~{round(improved*100)}% improved on the matched plan"
    return s


def select_best_diagnosis(outcome: DifferentialOutcome) -> Candidate | None:
    """Top statistical candidate backed by real cases (for treatment)."""
    backed = [c for c in outcome.candidates if c.similar_cases > 0 and not c.pinned_watch]
    if backed:
        return max(backed, key=lambda c: c.probability)
    return outcome.candidates[0] if outcome.candidates else None


async def build_treatment(
    session: AsyncSession,
    condition: str,
    patient: dict,
    *,
    reference_online: bool = True,
) -> dict:
    """Recommend a plan + screen it. Returns a v1/v2 treatment block dict.

    Safety is always screened against the English (canonical) medication names —
    the interaction/allergy reference is English-keyed, so screening the Chinese
    names would detect nothing. For a Chinese request the screened result is then
    mapped back to the parallel Chinese medications stored on the episode."""
    lang = patient.get("lang", "en")
    use_zh = lang == "zh"
    rec = await recommend_treatment(session, condition)
    screen = drug_safety.screen(rec.medications, patient, reference_online=reference_online)

    # EN drug name → the parallel ZH medication captured from the same episode.
    zh_by_drug = {
        (en_m.get("drug") or ""): zh_m
        for en_m, zh_m in zip(rec.medications, rec.medications_zh)
        if en_m.get("drug")
    }

    meds = []
    for m in screen.medications:
        en_drug = m.get("drug", "")
        zh_m = zh_by_drug.get(en_drug) if use_zh else None
        if zh_m:  # bilingual episode — render the stored Chinese medication
            meds.append(
                {
                    "drug": zh_m.get("drug") or en_drug,
                    "dose": zh_m.get("dose") or m.get("dose", ""),
                    "route": m.get("route", ""),
                    "frequency": m.get("frequency", ""),
                    "duration": zh_m.get("duration") or m.get("duration", ""),
                    "note": zh_m.get("note") or m.get("note", ""),
                }
            )
        else:  # English, or a safety-substituted alternative → code-map the name
            meds.append(
                {
                    "drug": drug_label(en_drug, lang),
                    "dose": m.get("dose", ""),
                    "route": m.get("route", ""),
                    "frequency": m.get("frequency", ""),
                    "duration": m.get("duration", ""),
                    "note": m.get("note", ""),
                }
            )
    safety = [{"severity": f.severity, "message": f.message} for f in screen.sorted_flags()]
    if screen.reduced_coverage:
        safety.append(
            {
                "severity": "Minor",
                "message": "Reduced coverage — external drug reference offline; "
                "local interaction set applied.",
            }
        )

    plan = rec.plan_zh if (use_zh and rec.plan_zh) else rec.plan
    rationale = rec.rationale
    monitoring = rec.monitoring
    if use_zh:
        rationale = (
            f"来自 {rec.n_cases} 个「{condition_label(condition, lang, rec.condition_zh)}」"
            f"既往病例；已通过药物安全筛查。"
            if rec.n_cases
            else "无匹配既往病例——治疗须由医师决定。"
        )
        monitoring = "48小时内复评；若症状加重或出现新的危险信号请立即返诊。"

    return {
        "bestDiagnosis": condition_label(condition, lang, rec.condition_zh),
        "icd": rec.icd,
        "rationale": rationale,
        "plan": plan,
        "medications": meds,
        "safety": safety,
        "monitoring": monitoring,
        "requiresPhysicianConfirmation": True,
        "_has_hard_block": screen.has_hard_block,
        "_drugref_version": screen.drugref_version,
    }


def to_v1_reply(outcome: DifferentialOutcome, lang: str, treatment: dict | None) -> dict:
    """Assemble the exact v1 chat contract (probability 0–100)."""
    summary = _summary_text(outcome, lang)
    items = []
    for c in outcome.candidates[:4]:
        band = band_for(c.probability, c.pinned_watch)
        items.append(
            {
                "condition": condition_label(c.condition, lang, c.condition_zh),
                "icd": c.icd or "",
                "probability": round(c.probability * 100, 1),
                "confidence": band,
                "because": _because(c, lang),
            }
        )
    lead = outcome.candidates[0] if outcome.candidates else None
    lead_test = lead.next_best_test if lead else ""
    lead_test_zh = lead.next_best_test_zh if lead else ""
    reply = {
        "redFlag": outcome.banner,
        "summary": summary,
        "differential": items,
        "nextBestTest": test_label(lead_test, lang, lead_test_zh),
        "treatment": _strip_internal(treatment) if treatment else None,
        "modelVersion": settings.model_version,
        "ruleSetVersion": settings.ruleset_version,
        "requiresPhysicianConfirmation": True,
        "degradedMode": outcome.degraded_mode,
        "ood": outcome.ood,
    }
    return reply


def _strip_internal(treatment: dict) -> dict:
    return {k: v for k, v in treatment.items() if not k.startswith("_")}
