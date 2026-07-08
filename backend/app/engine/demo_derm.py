"""Offline dermatology demo diagnoser (spec §7 — degraded/no-LLM operation).

When the GLM reasoning layer is not configured, MediSense still needs to give a
useful, *grounded* answer. This module is a deterministic, explainable matcher
that scores a free-text presentation directly against the clinical features in
the two dermatology core-data files (`dermatology_core_data_{EN,CN}.json`) —
key physical findings, chief-complaint templates, distribution, subtypes — and
returns a ranked differential, the KB's recommended workup, and its first-line,
insurance-tagged prescription with the KB's own safety alerts.

It is intentionally conservative: it only answers when the presentation is
clearly dermatological (≥2 distinct dermatology anchor terms and a real score),
so non-skin cases fall through to the general engine untouched. Every reply is
labelled demo mode and marked `requiresPhysicianConfirmation`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.engine.embeddings import _tokenize

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
EN_FILE = DATA_DIR / "dermatology_core_data_EN.json"
CN_FILE = DATA_DIR / "dermatology_core_data_CN.json"

_MIN_TOKENS = 3
_MIN_ANCHORS = 2  # distinct dermatology terms required to treat input as skin-related
_MIN_SCORE = 3.0

# Generic words stripped from feature bags so they neither match nor anchor.
_STOP = {
    "location", "duration", "age", "group", "for", "with", "and", "the", "of",
    "a", "an", "features", "changes", "substance", "present", "recurrent",
    "in", "on", "or", "to", "less", "than", "greater", "over", "time", "same",
    "site", "no", "not", "mild", "moderate", "severe", "acute", "chronic",
    "positive", "negative", "sign", "essential", "specific", "course",
}

# Curated dermatology anchor lexicon (in addition to every key-finding token,
# which is inherently dermatologic). Ultra-generic words (red, skin) are omitted.
_CURATED_ANCHORS = {
    "macule", "macules", "patch", "patches", "papule", "papules", "plaque",
    "plaques", "vesicle", "vesicles", "bulla", "bullae", "pustule", "pustules",
    "nodule", "nodules", "ulcer", "ulcers", "wheal", "wheals", "scale", "scales",
    "scaly", "crust", "crusts", "crusted", "lichenification", "silvery",
    "annular", "comedone", "comedones", "pruritic", "pruritus", "itchy",
    "itching", "telangiectasia", "pearly", "erythema", "erythematous", "lesion",
    "lesions", "rash", "mole", "moles", "nevus", "nevi", "pigmented", "blister",
    "blisters", "eczema", "eczematous", "acne", "psoriasis", "psoriatic",
    "dermatitis", "hives", "urticaria", "wart", "warts", "honey", "flaky",
    "flaking", "peeling", "hyperkeratotic", "keratin", "vesicular",
}

_VERSION = "demo-derm-1.0.0"


def _tok(text: str | None) -> list[str]:
    """Tokenize a feature phrase (underscores/slashes → spaces, then normalise)."""
    if not text:
        return []
    cleaned = text.replace("_", " ").replace("/", " ").replace("{", " ").replace("}", " ")
    return [t for t in _tokenize(cleaned) if t not in _STOP]


@lru_cache
def _index() -> tuple[list[dict], frozenset[str]]:
    """Build the per-condition weighted feature index + the global anchor set."""
    with open(EN_FILE, encoding="utf-8") as f:
        en = json.load(f)
    with open(CN_FILE, encoding="utf-8") as f:
        cn = json.load(f)

    cn_list = list(cn["conditions"].values())
    anchors: set[str] = set(_CURATED_ANCHORS)
    conditions: list[dict] = []

    for (slug, e), c in zip(en["conditions"].items(), cn_list, strict=False):
        if not e.get("prescriptions"):  # skip reference mnemonics (ABCDE, etc.)
            continue
        weights: dict[str, float] = {}

        def add(tokens: list[str], w: float, anchor: bool = False) -> None:
            for t in tokens:
                weights[t] = max(weights.get(t, 0.0), w)
                if anchor:
                    anchors.add(t)

        # English feature surfaces (weights: findings/name strongest).
        add(_tok(e.get("name")), 3.0, anchor=True)
        for f in e.get("key_physical_findings", []):
            add(_tok(f), 3.0, anchor=True)
        add(_tok(e.get("chief_complaint")), 1.5)
        for d in e.get("distribution", []):
            add(_tok(d), 1.5)
        for s in e.get("subtypes", []):
            add(_tok(s), 1.5)
        for r in e.get("risk_factors", []):
            add(_tok(r), 1.0)
        add(_tok(e.get("category")), 1.0)
        # Chinese surfaces so a zh presentation also matches.
        add(_tok(c.get("name")), 3.0, anchor=True)
        for f in c.get("关键体征", []):
            add(_tok(f), 3.0, anchor=True)
        add(_tok(c.get("主诉模板")), 1.5)

        conditions.append(
            {
                "slug": slug,
                "name_en": e.get("name", slug),
                "name_zh": e.get("name_cn") or c.get("name", ""),
                "icd": e.get("icd10", ""),
                "category": e.get("category", ""),
                "weights": weights,
                "findings_en": e.get("key_physical_findings", []),
                "findings_zh": c.get("关键体征", []),
                "labs_en": e.get("labs") or e.get("labs_baseline") or [],
                "labs_zh": c.get("检查") or c.get("基线检查") or [],
                "ddx_en": e.get("differential_diagnosis", []),
                "ddx_zh": c.get("鉴别诊断", []),
                "rx_en": e.get("prescriptions", {}),
                "rx_zh": c.get("处方", {}),
                "edu_en": e.get("education", []),
                "edu_zh": c.get("患者教育", []),
                "follow_en": e.get("follow_up", {}),
                "follow_zh": c.get("随访", {}),
            }
        )
    return conditions, frozenset(anchors)


# ── Malignant / do-not-miss categories → surfaced with a banner. ──────────────
_RED_FLAG_CATEGORIES = {"skin_cancer"}
_RED_FLAG_SLUGS = {"melanoma"}


def _is_red_flag(cond: dict) -> bool:
    return cond["category"] in _RED_FLAG_CATEGORIES or cond["slug"] in _RED_FLAG_SLUGS


def _matched_findings(cond: dict, qtokens: set[str], lang: str) -> list[str]:
    """Human-readable findings from this condition that the input supports."""
    phrases = cond["findings_zh"] if (lang == "zh" and cond["findings_zh"]) else cond["findings_en"]
    hits = []
    for phrase in phrases:
        if set(_tok(phrase)) & qtokens:
            hits.append(str(phrase).replace("_", " "))
    return hits[:3]


def _alert_flags(entry: dict, lang: str) -> list[dict]:
    """Map the KB's own RED/YELLOW/GREEN alert + contraindications to safety flags."""
    flags: list[dict] = []
    drug = entry.get("drug") or entry.get("药品") or entry.get("治疗") or ""
    alert = (entry.get("alert") or "").upper()
    special = entry.get("special") or entry.get("特殊说明") or ""
    contra = entry.get("contra") or entry.get("禁忌") or []
    zh = lang == "zh"
    if alert == "RED":
        flags.append(
            {
                "severity": "Major",
                "message": (f"{drug}：红色警示——高风险，需医师复核。{special}".strip())
                if zh
                else f"{drug}: RED alert — high-risk, requires physician override. {special}".strip(),
            }
        )
    elif alert == "YELLOW":
        flags.append(
            {
                "severity": "Moderate",
                "message": f"{drug}：黄色警示——需药师审核。" if zh
                else f"{drug}: YELLOW alert — pharmacist approval required.",
            }
        )
    elif alert == "GREEN":
        flags.append(
            {
                "severity": "Minor",
                "message": f"{drug}：绿色提醒——注意后可通过。" if zh
                else f"{drug}: GREEN — caution, pass with notice.",
            }
        )
    for cx in contra:
        flags.append(
            {
                "severity": "Contraindicated",
                "message": f"{drug} 在{cx}情况下禁用。" if zh else f"{drug} contraindicated in {cx}.",
            }
        )
    return flags


def _treatment_block(cond: dict, lang: str) -> dict:
    """First-line prescription + KB safety alerts for the top condition."""
    zh = lang == "zh"
    rx = cond["rx_zh"] if (zh and cond["rx_zh"]) else cond["rx_en"]
    name = cond["name_zh"] if zh else cond["name_en"]
    tiers = list(rx.items())
    tier_name, entries = tiers[0] if tiers else ("", [])

    meds: list[dict] = []
    plan: list[str] = []
    safety: list[dict] = []
    monitoring = ""
    for entry in entries:
        drug = entry.get("drug") or entry.get("药品") or entry.get("治疗")
        dose = entry.get("dose") or entry.get("用法") or ""
        dur = entry.get("duration") or entry.get("疗程") or ""
        note_bits = [
            entry.get("special") or entry.get("特殊说明") or "",
            ("医保" + entry["insurance"]) if entry.get("insurance") else "",
            ("医保" + entry["医保"]) if entry.get("医保") else "",
        ]
        note = "；".join(b for b in note_bits if b) if zh else "; ".join(b for b in note_bits if b)
        if drug:
            meds.append(
                {"drug": drug, "dose": dose, "route": "", "frequency": "", "duration": dur, "note": note}
            )
        elif entry.get("special") or entry.get("特殊"):
            plan.append(entry.get("特殊") if zh else entry.get("special"))
        safety += _alert_flags(entry, lang)
        monitoring = monitoring or entry.get("monitor") or entry.get("监测") or ""

    # Workup + education round out the plan.
    labs = cond["labs_zh"] if (zh and cond["labs_zh"]) else cond["labs_en"]
    if labs:
        first = str(labs[0]).replace("_", " ")
        plan.insert(0, (f"确诊检查：{first}" if zh else f"Confirm with: {first}"))
    edu = cond["edu_zh"] if (zh and cond["edu_zh"]) else cond["edu_en"]
    plan += [str(x) for x in edu[:2]]

    if not monitoring:
        follow = cond["follow_zh"] if (zh and cond["follow_zh"]) else cond["follow_en"]
        if follow:
            v = next(iter(follow.values()))
            monitoring = (f"随访：{v}" if zh else f"Follow-up: {v}")

    tier_label = tier_name.replace("_", " ")
    rationale = (
        f"皮肤科知识库中「{name}」的一线方案（{tier_label}）；请医师确认后使用。"
        if zh
        else f"First-line option for {name} from the dermatology KB ({tier_label}); physician confirms."
    )
    return {
        "bestDiagnosis": name,
        "icd": cond["icd"],
        "rationale": rationale,
        "plan": plan[:6],
        "medications": meds,
        "safety": safety,
        "monitoring": monitoring,
        "requiresPhysicianConfirmation": True,
    }


def _because(cond: dict, matched_findings: list[str], score_share: float, lang: str) -> str:
    if matched_findings:
        joined = "、".join(matched_findings) if lang == "zh" else ", ".join(matched_findings)
        return (f"符合：{joined}" if lang == "zh" else f"matches: {joined}")
    return ("特征部分匹配" if lang == "zh" else "partial feature match")


def diagnose(text: str, lang: str = "en") -> dict | None:
    """Return a v1 DiagnosisReply dict for a dermatological case, else None.

    None means "not confidently dermatological" — the caller then falls back to
    the general retrieval/classifier engine."""
    if not settings.demo_mode:
        return None
    qtokens = set(_tokenize(text))
    if len(qtokens) < _MIN_TOKENS:
        return None

    conditions, anchors = _index()
    if len(qtokens & anchors) < _MIN_ANCHORS:
        return None  # not clearly a skin presentation → let the general engine handle it

    scored: list[tuple[dict, float, set[str]]] = []
    for cond in conditions:
        matched = {t: cond["weights"][t] for t in qtokens if t in cond["weights"]}
        if matched:
            scored.append((cond, sum(matched.values()), set(matched)))
    if not scored:
        return None
    scored.sort(key=lambda r: r[1], reverse=True)
    if scored[0][1] < _MIN_SCORE:
        return None

    top_slice = scored[:4]
    total = sum(s for _, s, _ in top_slice) or 1.0

    zh = lang == "zh"
    differential = []
    red_flag = ""
    for cond, score, _matched in top_slice:
        share = round(score / total, 4)
        findings = _matched_findings(cond, qtokens, lang)
        pinned = _is_red_flag(cond)
        if pinned and not red_flag:
            red_flag = (
                "可能为皮肤恶性肿瘤——请优先皮肤科转诊并考虑活检。"
                if zh
                else "Possible skin malignancy — prioritize dermatology referral and biopsy."
            )
        band = "Watch" if pinned else ("High" if share >= 0.5 else "Moderate" if share >= 0.3 else "Low")
        differential.append(
            {
                "condition": cond["name_zh"] if zh else cond["name_en"],
                "icd": cond["icd"],
                "probability": round(share * 100, 1),
                "confidence": band,
                "because": _because(cond, findings, share, lang),
            }
        )

    top = scored[0][0]
    top_pct = differential[0]["probability"]
    top_name = differential[0]["condition"]
    summary = (
        f"首要考虑：{top_name}（约{top_pct:g}%）。"
        f"· 演示模式：基于皮肤科知识库的特征匹配（AI 推理未启用），医师须确认。"
        if zh
        else f"Leading consideration: {top_name} (~{top_pct:g}%). "
        f"· Demo mode: rule-based match over the dermatology KB (AI reasoning offline); physician confirms."
    )
    labs = top["labs_zh"] if (zh and top["labs_zh"]) else top["labs_en"]
    next_test = str(labs[0]).replace("_", " ") if labs else ""

    return {
        "redFlag": red_flag,
        "summary": summary,
        "differential": differential,
        "nextBestTest": next_test,
        "treatment": _treatment_block(top, lang),
        "modelVersion": _VERSION,
        "ruleSetVersion": settings.ruleset_version,
        "requiresPhysicianConfirmation": True,
        "degradedMode": False,
        "ood": False,
        "demoMode": True,
    }
