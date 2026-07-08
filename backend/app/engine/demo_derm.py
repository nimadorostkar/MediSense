"""Offline dermatology diagnoser (spec §7 — degraded / no-LLM operation).

When the GLM reasoning layer is not configured, MediSense still needs to give a
useful, *grounded* answer. This module is a deterministic, explainable clinical
matcher over the two dermatology core-data files
(`dermatology_core_data_{EN,CN}.json`). It is intentionally not a bag-of-words
lookup — token overlap alone lets generic words ("erythema", "papule") pull in
unrelated conditions. Instead it combines three signals so it ranks the way a
clinician reads a presentation:

1. **Distinctiveness (IDF).** A term appearing in few conditions ("silvery",
   "annular", "honey-colored", "comedones", "pearly", "Auspitz") is far more
   diagnostic than a common one; each term is weighted by inverse condition
   frequency computed over the KB itself.
2. **Coverage.** How much of a *condition's own defining picture* is present in
   the input — recall over its key findings — so a partial generic match can't
   outrank the condition whose full picture fits.
3. **Pruning + calibration.** Long-tail candidates that only share weak, common
   words are dropped; confidence is banded by evidence strength and the margin
   to the runner-up, never overclaimed.

Do-not-miss malignancies/emergencies are pinned as *Watch* whenever their
pathognomonic features appear, treatment is selected by detected severity, and
every reply is labelled demo mode and `requiresPhysicianConfirmation`.
"""

from __future__ import annotations

import json
import math
import re
from functools import lru_cache
from pathlib import Path

from app.config import settings
from app.engine.embeddings import _tokenize

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
EN_FILE = DATA_DIR / "dermatology_core_data_EN.json"
CN_FILE = DATA_DIR / "dermatology_core_data_CN.json"

_VERSION = "demo-derm-2.0.0"

_MIN_TOKENS = 3
_MIN_ANCHORS = 2  # distinct dermatology terms needed to treat input as skin-related
_PRUNE_RATIO = 0.22  # drop candidates scoring under this fraction of the leader
_MAX_DIFF = 4
_CONFIDENT_COVERAGE = 0.34  # top must explain this share of its findings to be "confident"
_DISTINCTIVE_DF = 3  # a term in ≤3 conditions is treated as diagnostic
_PATHOGNOMONIC_DF = 2  # a term in ≤2 conditions is near-unique (justifies a red-flag pin)

# Group weights (multiplied by each term's IDF at score time).
_W_FINDING = 3.0
_W_NAME = 3.0
_W_CHIEF = 1.6
_W_DIST = 1.4
_W_SUBTYPE = 1.4
_W_RISK = 1.0
_W_CATEGORY = 0.8

_STOP = {
    "location", "duration", "age", "group", "for", "with", "and", "the", "of",
    "a", "an", "features", "changes", "substance", "present", "recurrent",
    "in", "on", "or", "to", "less", "than", "greater", "over", "time", "same",
    "site", "no", "not", "mild", "moderate", "severe", "acute", "chronic",
    "positive", "negative", "sign", "essential", "specific", "course", "other",
    "one", "half", "unlike", "skin", "area", "areas", "surface", "surfaces",
    "growing", "growth", "appearance", "size", "shape", "raised", "active",
}

# Curated anchor lexicon (in addition to every key-finding token, which is
# inherently dermatologic). Ultra-generic words (red, skin) are omitted.
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
    "flaking", "peeling", "hyperkeratotic", "keratin", "vesicular", "burrows",
    "flushing", "dermatomal", "blistering", "erosions",
}

# Do-not-miss conditions surfaced even at low probability.
_RED_FLAG_CATEGORIES = {"skin_cancer"}
_RED_FLAG_SLUGS = {"melanoma", "pemphigus_vulgaris", "sjs_ten", "bullous_pemphigoid"}

_NEG_MARKERS = {"no", "without", "denies", "denied", "deny", "absent", "not", "negative"}
_SEVERE_WORDS = {
    "severe", "widespread", "extensive", "generalized", "nodulocystic", "cysts",
    "cystic", "confluent", "systemic", "disabling", "erythroderma", "metastatic",
    "ulcerated", "rapidly",
}
_MODERATE_WORDS = {"moderate", "multiple", "many", "numerous", "spreading", "worsening"}


# ── Canonical term normalisation ─────────────────────────────────────────────
# Morphological variants (scale/scales/scaly) and lay synonyms (silver→silvery,
# blackhead→comedone, ring→annular) are collapsed to ONE canonical token,
# applied to BOTH the KB (at index build) and the query, so real-world phrasing
# reaches the right findings while matching stays deterministic and grounded.
_CANON: dict[str, str] = {
    # scale family
    "scales": "scale", "scaly": "scale", "scaling": "scale", "flaky": "scale",
    "flaking": "scale", "flakes": "scale", "flake": "scale", "dandruff": "scale",
    "desquamation": "scale", "peeling": "scale",
    # plaque / patch
    "plaques": "plaque", "patches": "patch",
    # papule / pimple
    "papules": "papule", "pimple": "papule", "pimples": "papule", "zit": "papule",
    "zits": "papule", "bump": "papule", "bumps": "papule",
    # pustule
    "pustules": "pustule", "pus": "pustule",
    # comedone
    "comedones": "comedone", "blackhead": "comedone", "blackheads": "comedone",
    "whitehead": "comedone", "whiteheads": "comedone", "comedo": "comedone",
    # vesicle / blister
    "vesicles": "vesicle", "vesicular": "vesicle", "blister": "vesicle",
    "blisters": "vesicle", "blistering": "vesicle", "bleb": "vesicle",
    # bulla
    "bullae": "bulla",
    # nodule / lump
    "nodules": "nodule", "lump": "nodule", "lumps": "nodule",
    # ulcer / sore
    "ulcers": "ulcer", "ulcerated": "ulcer", "ulceration": "ulcer", "sore": "ulcer",
    "sores": "ulcer",
    # crust / scab
    "crusts": "crust", "crusty": "crust", "crusted": "crust", "scab": "crust",
    "scabs": "crust",
    # erosion
    "erosions": "erosion", "raw": "erosion",
    # silvery
    "silvery": "silver", "silverish": "silver", "silverwhite": "silver",
    # itch / pruritus
    "pruritic": "itch", "pruritus": "itch", "itchy": "itch", "itching": "itch",
    "itches": "itch", "itchiness": "itch",
    # erythema / red
    "erythematous": "erythema", "red": "erythema", "redness": "erythema",
    "reddened": "erythema",
    # annular / ring
    "ring": "annular", "ringshaped": "annular", "ringlike": "annular",
    "ringworm": "annular", "circular": "annular", "circinate": "annular",
    # pearly / shiny
    "shiny": "pearly", "waxy": "pearly", "translucent": "pearly", "glistening": "pearly",
    # telangiectasia
    "telangiectasias": "telangiectasia",
    # wheal / hive
    "wheals": "wheal", "hives": "wheal", "hive": "wheal", "welts": "wheal", "welt": "wheal",
    # mole / nevus
    "moles": "mole", "nevus": "mole", "nevi": "mole", "naevus": "mole", "naevi": "mole",
    # pigment
    "pigmented": "pigment", "dark": "pigment", "darkened": "pigment",
    "brownish": "pigment", "discolored": "pigment", "discoloured": "pigment",
    # demarcated / defined
    "demarcated": "demarcate", "defined": "demarcate", "bordered": "demarcate",
    # honey / golden
    "golden": "honey", "honeycolored": "honey", "honeycoloured": "honey",
    # flushing
    "flushed": "flush", "flushing": "flush", "blushing": "flush",
}

# Multi-word cues → canonical tokens (applied before word canonicalisation).
_PHRASE_SYN: list[tuple[str, set[str]]] = [
    ("ring shaped", {"annular"}), ("ring-shaped", {"annular"}), ("ring like", {"annular"}),
    ("blood vessels", {"telangiectasia"}), ("broken vessels", {"telangiectasia"}),
    ("spider veins", {"telangiectasia"}), ("spider vein", {"telangiectasia"}),
    ("honey colored", {"honey"}), ("honey coloured", {"honey"}), ("honey-colored", {"honey"}),
    ("clear middle", {"central", "clearing"}), ("clear centre", {"central", "clearing"}),
    ("clear center", {"central", "clearing"}),
    ("wont heal", {"ulcer"}), ("won't heal", {"ulcer"}), ("not healing", {"ulcer"}),
    ("non healing", {"ulcer"}), ("non-healing", {"ulcer"}),
    ("sun damaged", {"sun", "exposed"}), ("sun exposed", {"sun", "exposed"}),
]


def _canon(t: str) -> str:
    return _CANON.get(t, t)


def _tok(text: str | None) -> list[str]:
    """Tokenize a feature phrase → canonical tokens (variants/synonyms collapsed)."""
    if not text:
        return []
    cleaned = re.sub(r"[_/{}()]", " ", text)
    return [
        _canon(t)
        for t in _tokenize(cleaned)
        if t not in _STOP and not t.isdigit()
    ]


def _expand_tokens(text: str) -> set[str]:
    """Query → canonical token set (word + multi-word synonyms applied)."""
    low = text.lower()
    tokens = {_canon(t) for t in _tokenize(text) if t not in _STOP}
    for phrase, adds in _PHRASE_SYN:
        if phrase in low:
            tokens |= {_canon(a) for a in adds}
    return tokens


@lru_cache
def _index() -> tuple[list[dict], dict[str, float], frozenset[str]]:
    """Build the per-condition feature index, the IDF map, and the anchor set."""
    with open(EN_FILE, encoding="utf-8") as f:
        en = json.load(f)
    with open(CN_FILE, encoding="utf-8") as f:
        cn = json.load(f)

    cn_list = list(cn["conditions"].values())
    anchors: set[str] = {_canon(a) for a in _CURATED_ANCHORS}
    conditions: list[dict] = []

    for (slug, e), c in zip(en["conditions"].items(), cn_list, strict=False):
        if not e.get("prescriptions"):  # skip reference mnemonics (ABCDE, etc.)
            continue

        weights: dict[str, float] = {}
        finding_tok_sets: list[tuple[str, set[str]]] = []  # (phrase, token-set) for coverage

        def add(tokens: list[str], w: float, anchor: bool = False) -> None:
            for t in tokens:
                weights[t] = max(weights.get(t, 0.0), w)
                if anchor:
                    anchors.add(t)

        add(_tok(e.get("name")), _W_NAME, anchor=True)
        for phrase in e.get("key_physical_findings", []):
            toks = _tok(phrase)
            add(toks, _W_FINDING, anchor=True)
            if toks:
                finding_tok_sets.append((str(phrase).replace("_", " "), set(toks)))
        add(_tok(e.get("chief_complaint")), _W_CHIEF)
        for d in e.get("distribution", []):
            add(_tok(d), _W_DIST)
        for s in e.get("subtypes", []):
            add(_tok(s), _W_SUBTYPE)
        for r in e.get("risk_factors", []):
            add(_tok(r), _W_RISK)
        add(_tok(e.get("category")), _W_CATEGORY)
        # Chinese surfaces so a zh presentation also matches.
        add(_tok(c.get("name")), _W_NAME, anchor=True)
        for phrase in c.get("关键体征", []):
            toks = _tok(phrase)
            add(toks, _W_FINDING, anchor=True)
            if toks:
                finding_tok_sets.append((str(phrase), set(toks)))
        add(_tok(c.get("主诉模板")), _W_CHIEF)

        conditions.append(
            {
                "slug": slug,
                "name_en": e.get("name", slug),
                "name_zh": e.get("name_cn") or c.get("name", ""),
                "icd": e.get("icd10", ""),
                "category": e.get("category", ""),
                "weights": weights,
                "terms": frozenset(weights),
                "finding_sets": finding_tok_sets,
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

    # Inverse-condition-frequency: a term in few conditions is more diagnostic.
    n = len(conditions)
    df: dict[str, int] = {}
    for cond in conditions:
        for t in cond["terms"]:
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log((n + 1) / (d + 1)) + 1.0 for t, d in df.items()}
    for cond in conditions:
        cond["distinctive"] = frozenset(t for t in cond["terms"] if df.get(t, n) <= _DISTINCTIVE_DF)
        # Near-unique terms — treated as pathognomonic; only these justify raising
        # a malignancy/emergency banner for a *trailing* candidate.
        cond["pathognomonic"] = frozenset(t for t in cond["terms"] if df.get(t, n) <= _PATHOGNOMONIC_DF)

    return conditions, idf, frozenset(anchors)


def anchor_count(text: str) -> int:
    """Number of distinct dermatology anchor terms in `text` (for intent routing)."""
    _, _, anchors = _index()
    return len(_expand_tokens(text) & anchors)


def _is_red_flag(cond: dict) -> bool:
    return cond["category"] in _RED_FLAG_CATEGORIES or cond["slug"] in _RED_FLAG_SLUGS


def _negated_tokens(text: str) -> set[str]:
    """Tokens explicitly negated ('no scale', 'denies pain') → discount them."""
    words = re.sub(r"[^\w\s]", " ", text.lower()).split()
    out: set[str] = set()
    for i, w in enumerate(words):
        if w in _NEG_MARKERS:
            for nxt in words[i + 1 : i + 4]:
                out.update(_tok(nxt))
    return out


def _severity(text: str) -> str:
    toks = set(_tokenize(text))
    if toks & _SEVERE_WORDS:
        return "severe"
    if toks & _MODERATE_WORDS:
        return "moderate"
    return "mild"


def _score(cond: dict, qtokens: set[str], negated: set[str], idf: dict[str, float]) -> dict:
    """Score one condition: evidence mass × finding-coverage, distinctiveness-boosted."""
    matched = {t: cond["weights"][t] * idf.get(t, 1.0) for t in qtokens & cond["terms"]}
    if not matched:
        return {"score": 0.0}
    # Discount findings the clinician explicitly negated.
    for t in negated & cond["terms"]:
        matched.pop(t, None)
    if not matched:
        return {"score": 0.0}

    raw = sum(matched.values())
    covered = [ph for ph, ts in cond["finding_sets"] if ts & qtokens]
    coverage = len(covered) / max(1, len(cond["finding_sets"]))
    distinctive_hits = sorted(
        (t for t in matched if t in cond["distinctive"]),
        key=lambda t: idf.get(t, 1.0),
        reverse=True,
    )
    score = raw * (0.5 + 0.5 * coverage) + 0.6 * len(distinctive_hits)
    return {
        "cond": cond,
        "score": round(score, 4),
        "matched": matched,
        "coverage": coverage,
        "covered_findings": covered,
        "distinctive_hits": distinctive_hits,
    }


def _matched_findings(res: dict, lang: str) -> list[str]:
    """Human-readable defining findings the input supports (distinctive first)."""
    cond = res["cond"]
    zh = lang == "zh" and cond["findings_zh"]
    phrases = cond["findings_zh"] if zh else cond["findings_en"]
    qtokens = set(res["matched"])
    scored = []
    for phrase in phrases:
        toks = set(_tok(phrase))
        hit = toks & qtokens
        if hit:
            weight = max(res["matched"].get(t, 0.0) for t in hit)
            scored.append((weight, str(phrase).replace("_", " ")))
    scored.sort(reverse=True)
    return [p for _, p in scored[:3]]


def _differentiators(cond: dict, lang: str, limit: int = 2) -> list[str]:
    zh = lang == "zh" and cond["ddx_zh"]
    ddx = cond["ddx_zh"] if zh else cond["ddx_en"]
    out = []
    for d in ddx[:limit]:
        if zh:
            out.append(f"与{d.get('疾病','')}鉴别：{d.get('鉴别要点','')}")
        else:
            out.append(f"vs {d.get('disease','')}: {d.get('differentiator','')}")
    return out


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


def _tier_for_severity(keys: list[str], severity: str) -> int:
    """Pick the prescription tier (mild→first … severe→last) matching severity."""
    n = len(keys)
    if n <= 1:
        return 0
    low = [k.lower() for k in keys]
    if severity == "severe":
        for i, k in enumerate(low):
            if any(w in k for w in ("severe", "biolog", "systemic", "oncolog", "metastat", "advanced")):
                return i
        return n - 1
    if severity == "moderate":
        for i, k in enumerate(low):
            if "moderate" in k or "systemic" in k:
                return i
        return min(1, n - 1)
    return 0


def _treatment_block(res: dict, lang: str, severity: str) -> dict:
    """Severity-appropriate first-line prescription + KB safety alerts."""
    cond = res["cond"]
    zh = lang == "zh"
    rx = cond["rx_zh"] if (zh and cond["rx_zh"]) else cond["rx_en"]
    name = cond["name_zh"] if zh else cond["name_en"]
    tiers = list(rx.items())
    if not tiers:
        return {}
    idx = _tier_for_severity([k for k, _ in tiers], severity)
    tier_name, entries = tiers[idx]

    meds: list[dict] = []
    plan: list[str] = []
    safety: list[dict] = []
    monitoring = ""
    for entry in entries:
        drug = entry.get("drug") or entry.get("药品") or entry.get("治疗")
        dose = entry.get("dose") or entry.get("用法") or ""
        dur = entry.get("duration") or entry.get("疗程") or ""
        if zh:
            note_bits = [
                entry.get("特殊说明") or entry.get("special") or "",
                ("医保" + entry["医保"]) if entry.get("医保") else "",
            ]
            note = "；".join(b for b in note_bits if b)
        else:
            insurance = (entry.get("insurance") or "").replace("Class_", "Class ").replace("_", " ")
            note_bits = [entry.get("special") or "", (f"Insurance: {insurance}") if insurance else ""]
            note = "; ".join(b for b in note_bits if b)
        if drug:
            meds.append(
                {"drug": drug, "dose": dose, "route": "", "frequency": "", "duration": dur, "note": note}
            )
        elif entry.get("special") or entry.get("特殊"):
            plan.append(entry.get("特殊") if zh else entry.get("special"))
        safety += _alert_flags(entry, lang)
        monitoring = monitoring or entry.get("monitor") or entry.get("监测") or ""

    labs = cond["labs_zh"] if (zh and cond["labs_zh"]) else cond["labs_en"]
    if labs:
        first = str(labs[0]).replace("_", " ")
        plan.insert(0, (f"确诊检查：{first}" if zh else f"Confirm with: {first}"))
    edu = cond["edu_zh"] if (zh and cond["edu_zh"]) else cond["edu_en"]
    plan += [str(x) for x in edu[:2]]

    if not monitoring:
        follow = cond["follow_zh"] if (zh and cond["follow_zh"]) else cond["follow_en"]
        if follow:
            monitoring = (f"随访：{next(iter(follow.values()))}" if zh
                          else f"Follow-up: {next(iter(follow.values()))}")

    tier_label = tier_name.replace("_", " ")
    sev_zh = {"mild": "轻", "moderate": "中", "severe": "重"}[severity]
    rationale = (
        f"皮肤科知识库中「{name}」的方案（{tier_label}，按{sev_zh}度）；请医师确认。"
        if zh
        else f"Option for {name} from the dermatology KB ({tier_label}; {severity} severity); physician confirms."
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


def _band(share: float, coverage: float, distinctive: int, pinned: bool) -> str:
    if pinned:
        return "Watch"
    if share >= 0.45 and coverage >= 0.4 and distinctive >= 1:
        return "High"
    if share >= 0.5 and distinctive >= 2:
        return "High"
    if share >= 0.28:
        return "Moderate"
    return "Low"


def diagnose(text: str, lang: str = "en") -> dict | None:
    """Return a v1 DiagnosisReply dict for a dermatological case, else None.

    None means "not confidently dermatological" — the caller falls back to the
    general retrieval/classifier engine."""
    if not settings.demo_mode:
        return None
    if len(_tokenize(text)) < _MIN_TOKENS:
        return None
    # Expand lay/synonym terms to the KB's clinical vocabulary before matching.
    qtokens = _expand_tokens(text)

    conditions, idf, anchors = _index()
    if len(qtokens & anchors) < _MIN_ANCHORS:
        return None  # not clearly a skin presentation → let the general engine handle it

    negated = _negated_tokens(text)
    severity = _severity(text)

    scored = [r for r in (_score(c, qtokens, negated, idf) for c in conditions) if r["score"] > 0]
    if not scored:
        return None
    scored.sort(key=lambda r: r["score"], reverse=True)

    top = scored[0]
    threshold = _PRUNE_RATIO * top["score"]

    def _substantive(r: dict) -> bool:
        # A trailing candidate must genuinely explain part of the picture — a
        # distinctive (rare) term, or ≥2 of its own defining findings — not merely
        # share a common word.
        return bool(r["distinctive_hits"]) or len(r["covered_findings"]) >= 2

    keep = [top]
    for r in scored[1:]:
        if len(keep) >= _MAX_DIFF:
            break
        if r["score"] >= threshold and _substantive(r):
            keep.append(r)

    # Pathognomonic hit = a near-unique term of that condition present in the input.
    for r in scored:
        r["path_hits"] = len(set(r["matched"]) & r["cond"]["pathognomonic"]) if r.get("matched") else 0

    # Surface a do-not-miss condition even if pruned, but only when its *defining*
    # picture is present (pathognomonic term + real coverage), not one shared word.
    kept_slugs = {r["cond"]["slug"] for r in keep}
    for r in scored:
        if len(keep) >= _MAX_DIFF + 1:
            break
        if (
            _is_red_flag(r["cond"])
            and r["cond"]["slug"] not in kept_slugs
            and r["path_hits"]
            and r["coverage"] >= _CONFIDENT_COVERAGE
        ):
            keep.append(r)
            kept_slugs.add(r["cond"]["slug"])

    # Display filter: never show a *trailing* candidate that matched none of its
    # own defining findings ("partial feature match") — it reads as noise. The
    # leading call and any pathognomonically-pinned red flag always survive.
    keep = [keep[0]] + [r for r in keep[1:] if r["covered_findings"]]

    total = sum(r["score"] for r in keep) or 1.0
    zh = lang == "zh"

    # Confidence in the leading call: enough of its own picture, or a clear margin.
    top_share = top["score"] / total
    runner = keep[1]["score"] / total if len(keep) > 1 else 0.0
    confident = (
        top["coverage"] >= _CONFIDENT_COVERAGE
        or len(top["distinctive_hits"]) >= 2
        or (top_share - runner) >= 0.25
    )

    differential = []
    red_flag = ""
    for rank, r in enumerate(keep):
        cond = r["cond"]
        share = round(r["score"] / total, 4)
        # A trailing malignancy/emergency is only pinned (and only raises the
        # banner) when its defining picture is present — a pathognomonic feature
        # AND real coverage — not a single word shared with a benign look-alike.
        pinned = (
            _is_red_flag(cond)
            and rank > 0
            and share < 0.30
            and r["path_hits"] >= 1
            and r["coverage"] >= _CONFIDENT_COVERAGE
        )
        findings = _matched_findings(r, lang)
        banner_worthy = _is_red_flag(cond) and (rank == 0 or share >= 0.30 or pinned)
        if banner_worthy and not red_flag:
            red_flag = (
                "可能为皮肤恶性肿瘤或重症皮肤病——请优先皮肤科转诊并考虑活检。"
                if zh
                else "Possible skin malignancy / serious dermatosis — prioritize dermatology referral and biopsy."
            )
        band = _band(share, r["coverage"], len(r["distinctive_hits"]), pinned)
        if not confident and not pinned:
            band = "Low" if band in ("Moderate", "Low") else band
        because = (
            (("符合：" if zh else "matches: ") + ("、".join(findings) if zh else ", ".join(findings)))
            if findings
            else ("特征部分匹配" if zh else "partial feature match")
        )
        differential.append(
            {
                "condition": cond["name_zh"] if zh else cond["name_en"],
                "icd": cond["icd"],
                "probability": min(round(share * 100, 1), 95.0),  # never overclaim certainty
                "confidence": band,
                "because": because,
            }
        )

    top_cond = top["cond"]
    top_name = differential[0]["condition"]
    top_pct = differential[0]["probability"]
    diffs = _differentiators(top_cond, lang)
    disclaimer = (
        "· 演示模式：基于皮肤科知识库的特征匹配（AI 推理未启用），医师须确认。"
        if zh
        else "· Demo mode: feature match over the dermatology KB (AI reasoning offline); physician confirms."
    )

    # Only name a diagnosis on real diagnostic signal: a distinctive (rare) term
    # or ≥2 covered findings. Matching only generic words ("red", "itchy") is too
    # little → ask for the morphology instead of guessing (especially a cancer).
    insufficient = not top["distinctive_hits"] and len(top["covered_findings"]) < 2
    if insufficient:
        ask = (
            "描述尚不足以做出皮肤科诊断。请补充皮损形态（斑疹/丘疹/斑块/水疱/脓疱/鳞屑/痂）、"
            "分布部位、颜色与病程，以便生成鉴别诊断。"
            if zh
            else "The description isn't specific enough for a dermatological diagnosis. Please add lesion "
            "morphology (macule, papule, plaque, vesicle, pustule, scale, crust), distribution/location, "
            "colour, and duration so a differential can be formed."
        )
        return {
            "redFlag": "",
            "summary": f"{ask} {disclaimer}",
            "differential": [],
            "nextBestTest": "",
            "treatment": None,
            "modelVersion": _VERSION,
            "ruleSetVersion": settings.ruleset_version,
            "requiresPhysicianConfirmation": True,
            "degradedMode": False,
            "ood": True,
            "demoMode": True,
        }

    if confident:
        lead = (
            f"首要考虑：{top_name}（约{top_pct:g}%）。"
            if zh
            else f"Leading consideration: {top_name} (~{top_pct:g}%)."
        )
        if diffs:
            lead += ("　鉴别：" + "；".join(diffs) if zh else "  Differentiators — " + "; ".join(diffs))
    else:
        # Neutral — present the possibilities without singling out (a cancer).
        names = "、".join(d["condition"] for d in differential[:3]) if zh else ", ".join(
            d["condition"] for d in differential[:3]
        )
        lead = (
            f"特征尚不特异。可能的考虑：{names}。请补充皮损形态、分布与病程以缩小鉴别。"
            if zh
            else f"Findings are not yet specific. Possible considerations: {names}. "
            "Add lesion morphology, distribution, and duration to narrow the differential."
        )
    summary = f"{lead} {disclaimer}"

    labs = top_cond["labs_zh"] if (zh and top_cond["labs_zh"]) else top_cond["labs_en"]
    next_test = str(labs[0]).replace("_", " ") if labs else ""

    reply = {
        "redFlag": red_flag,
        "summary": summary,
        "differential": differential,
        "nextBestTest": next_test,
        # Only recommend a plan when the leading diagnosis is reasonably supported.
        "treatment": _treatment_block(top, lang, severity) if confident else None,
        "modelVersion": _VERSION,
        "ruleSetVersion": settings.ruleset_version,
        "requiresPhysicianConfirmation": True,
        "degradedMode": False,
        "ood": not confident,
        "demoMode": True,
    }
    return reply
