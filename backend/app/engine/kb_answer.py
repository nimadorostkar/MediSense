"""File-grounded follow-up answerer — answers ONLY from the uploaded data files.

An informational question in the chat ("what dose?", "is it safe in pregnancy?",
"why X and not Y?", "which test confirms it?") is answered HERE,
deterministically, from the same uploaded knowledge files that power diagnosis
(`dermatology_core_data_{EN,CN}.json`, `drug_reference.json`). No language model
is ever consulted: every line of the answer is copied or templated from a file
field. When the files do not contain the requested information the module
returns None and the caller replies that the information is not in the uploaded
files — it never guesses and never falls back to AI knowledge.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from app.engine import demo_derm

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DRUG_REF_FILE = DATA_DIR / "drug_reference.json"

_WORD_RE = re.compile(r"[a-z]+")

_MAX_LINES = 16

_FOOTER = {
    "en": "— Answered strictly from the uploaded knowledge files.",
    "zh": "——回答内容完全来自已上传的资料文件。",
}

# ── Question facets (EN exact-token / ZH substring) ──────────────────────────
_FACETS_EN: dict[str, frozenset[str]] = {
    "treatment": frozenset({
        "dose", "doses", "dosage", "dosing", "prescribe", "prescription",
        "prescribing", "treat", "treatment", "treatments", "therapy",
        "medication", "medications", "drug", "drugs", "regimen", "rx",
        "manage", "management",
    }),
    "safety": frozenset({
        "safe", "safety", "pregnant", "pregnancy", "breastfeed", "breastfeeding",
        "lactation", "contraindication", "contraindicated", "contraindications",
        "adverse", "interaction", "interactions", "interact", "monitor",
        "monitoring", "warning", "warnings", "risk", "risks", "alert", "alerts",
    }),
    "differential": frozenset({
        "why", "versus", "vs", "instead", "differ", "difference", "differences",
        "differentiate", "distinguish", "differential", "compare", "comparison",
    }),
    "tests": frozenset({
        "test", "tests", "lab", "labs", "biopsy", "confirm", "confirms",
        "confirmation", "workup", "investigation", "investigations", "koh",
        "dermoscopy", "serology", "culture",
    }),
    "followup": frozenset({"follow", "review", "recheck", "revisit"}),
    "education": frozenset({
        "advice", "advise", "education", "educate", "counsel", "counselling",
        "counseling", "lifestyle", "avoid", "prevention", "prevent",
    }),
    "findings": frozenset({
        "finding", "findings", "feature", "features", "sign", "signs",
        "presentation", "morphology", "appearance",
    }),
}
_FACETS_ZH: dict[str, tuple[str, ...]] = {
    "treatment": ("剂量", "用量", "处方", "治疗", "用药", "开药", "什么药", "疗程", "方案", "怎么治"),
    "safety": ("安全", "孕", "妊娠", "哺乳", "禁忌", "副作用", "不良反应", "相互作用", "监测", "风险"),
    "differential": ("为什么", "为何", "鉴别", "区别", "区分", "而不是"),
    "tests": ("检查", "化验", "活检", "确诊", "镜检"),
    "followup": ("随访", "复诊", "复查"),
    "education": ("宣教", "患者教育", "注意事项", "预防", "避免"),
    "findings": ("表现", "体征", "特征", "形态", "皮损特点"),
}

# Dose-form / filler words that never identify a drug on their own.
_DRUG_FORM_WORDS = frozenset({
    "ointment", "cream", "gel", "capsule", "capsules", "tablet", "tablets",
    "solution", "lotion", "shampoo", "wash", "spray", "foam", "injection",
    "patch", "oral", "topical", "acid", "with", "plus", "sodium", "based",
})
# Name tokens too generic to identify a condition even when unique in the KB.
_NAME_TOKEN_BLACKLIST = frozenset({"ten", "rule", "sign", "drug", "induced"})


def _q_tokens(question: str) -> frozenset[str]:
    return frozenset(_WORD_RE.findall(question.lower()))


def _facets(question: str) -> set[str]:
    toks = _q_tokens(question)
    hit = {f for f, words in _FACETS_EN.items() if toks & words}
    hit |= {f for f, subs in _FACETS_ZH.items() if any(s in question for s in subs)}
    return hit


def _name(cond: dict, zh: bool) -> str:
    return cond["name_zh"] if (zh and cond["name_zh"]) else cond["name_en"]


@lru_cache
def _condition_aliases() -> list[dict]:
    """Per KB condition: full-name phrases, unique name tokens, Chinese names."""
    conditions, _, _ = demo_derm._index()
    name_tokens: dict[str, set[str]] = {}
    for c in conditions:
        surface = f"{c['name_en']} {c['slug'].replace('_', ' ')}".lower()
        name_tokens[c["slug"]] = set(_WORD_RE.findall(surface)) - _NAME_TOKEN_BLACKLIST
    df: dict[str, int] = {}
    for toks in name_tokens.values():
        for t in toks:
            df[t] = df.get(t, 0) + 1
    out = []
    for c in conditions:
        out.append(
            {
                "cond": c,
                "phrases": {c["name_en"].lower(), c["slug"].replace("_", " ")},
                "tokens": {t for t in name_tokens[c["slug"]] if df[t] == 1 and len(t) >= 3},
                "zh_names": {n for n in (c["name_zh"],) if n},
            }
        )
    return out


def _named_conditions(question: str) -> list[dict]:
    """KB conditions explicitly named in the question, in order of appearance."""
    q_low = question.lower()
    toks = _q_tokens(question)
    hits: list[tuple[int, dict]] = []
    for a in _condition_aliases():
        pos: int | None = None
        for phrase in a["phrases"]:
            i = q_low.find(phrase)
            if i >= 0:
                pos = i if pos is None else min(pos, i)
        for zh in a["zh_names"]:
            i = question.find(zh)
            if i >= 0:
                pos = i if pos is None else min(pos, i)
        if pos is None:
            for t in a["tokens"]:
                if t in toks:
                    i = q_low.find(t)
                    pos = i if pos is None else min(pos, i)
        if pos is not None:
            hits.append((pos, a["cond"]))
    hits.sort(key=lambda h: h[0])
    return [c for _, c in hits]


def _condition_from_reply(last_reply: dict | None) -> dict | None:
    """Map the leading condition of the last grounded reply back to its KB entry."""
    if not last_reply:
        return None
    diff = last_reply.get("differential") or []
    if not diff:
        return None
    lead = (diff[0].get("condition") or "").strip().lower()
    if not lead:
        return None
    for a in _condition_aliases():
        c = a["cond"]
        if lead in (c["name_en"].lower(), (c["name_zh"] or "").lower()):
            return c
    return None


@lru_cache
def _drug_index() -> tuple[dict[str, list], list[tuple[str, dict]]]:
    """Every prescription entry in the KB files, keyed by drug-name token (EN)
    and by Chinese drug name (substring match)."""
    conditions, _, _ = demo_derm._index()
    by_token: dict[str, list] = {}
    zh_names: list[tuple[str, dict]] = []
    for c in conditions:
        for tier, entries in (c["rx_en"] or {}).items():
            for entry in entries:
                drug = entry.get("drug") or ""
                if not drug:
                    continue
                match = {"cond": c, "tier": tier, "entry": entry}
                for t in _WORD_RE.findall(drug.lower()):
                    if len(t) >= 4 and t not in _DRUG_FORM_WORDS:
                        by_token.setdefault(t, []).append(match)
                zh_drug = entry.get("drug_cn") or ""
                if len(zh_drug) >= 2:
                    zh_names.append((zh_drug, match))
        for tier, entries in (c["rx_zh"] or {}).items():
            for entry in entries:
                zh_drug = entry.get("药品") or entry.get("drug") or ""
                if len(zh_drug) >= 2:
                    zh_names.append((zh_drug, {"cond": c, "tier": tier, "entry": entry}))
    return by_token, zh_names


def _named_drugs(question: str) -> list[dict]:
    """Prescription entries whose drug name appears in the question."""
    by_token, zh_names = _drug_index()
    toks = _q_tokens(question)
    matches: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for t in toks:
        for m in by_token.get(t, []):
            key = (m["entry"].get("drug", ""), m["entry"].get("dose", ""))
            if key not in seen:
                seen.add(key)
                matches.append(m)
    for zh_drug, m in zh_names:
        if zh_drug in question:
            e = m["entry"]
            key = (e.get("drug") or e.get("药品") or "", e.get("dose") or e.get("用法") or "")
            if key not in seen:
                seen.add(key)
                matches.append(m)
    return matches


# ── Section renderers (every line templated from file fields) ────────────────


def _render_drug(match: dict, zh: bool) -> list[str]:
    e, c = match["entry"], match["cond"]
    if zh:
        drug = e.get("drug_cn") or e.get("药品") or e.get("drug") or ""
    else:
        drug = e.get("drug") or e.get("药品") or ""
    dose = e.get("dose") or e.get("用法") or ""
    dur = e.get("duration") or e.get("疗程") or ""
    monitor = e.get("monitor") or e.get("监测") or ""
    special = e.get("special") or e.get("特殊说明") or ""
    contra = e.get("contra") or e.get("禁忌") or []
    alert = (e.get("alert") or "").upper()
    tier = match["tier"].replace("_", " ")
    cname = _name(c, zh)
    lines = [f"{drug}（用于{cname}，{tier}）：" if zh else f"{drug} (for {cname}, {tier}):"]
    if dose:
        d = f"• 用法：{dose}" if zh else f"• Dose: {dose}"
        if dur:
            d += f"；疗程：{dur}" if zh else f"; duration: {dur}"
        lines.append(d)
    if monitor:
        lines.append(f"• 监测：{monitor}" if zh else f"• Monitor: {monitor}")
    if special:
        lines.append(f"• 说明：{special}" if zh else f"• Note: {special}")
    if contra:
        joined = "、".join(contra) if zh else ", ".join(contra)
        lines.append(f"• 禁忌：{joined}" if zh else f"• Contraindicated in: {joined}")
    if alert:
        lines.append(f"• 警示级别：{alert}" if zh else f"• Alert level: {alert}")
    return lines


_PREG_WORDS = ("pregnan", "contracept", "breastfeed", "lactation", "孕", "妊娠", "哺乳", "避孕")


def _asks_pregnancy(question: str) -> bool:
    q = question.lower()
    return any(w in q or w in question for w in _PREG_WORDS)


def _sec_safety(c: dict, question: str, lang: str) -> list[str]:
    zh = lang == "zh"
    preg_only = _asks_pregnancy(question)
    lines: list[str] = []
    rx = c["rx_zh"] if (zh and c["rx_zh"]) else c["rx_en"]
    for entries in (rx or {}).values():
        for e in entries:
            for flag in demo_derm._alert_flags(e, lang):
                lines.append(f"• {flag['message']}")
            monitor = e.get("monitor") or e.get("监测") or ""
            if monitor:
                drug = (e.get("drug_cn") or e.get("药品") or e.get("drug")) if zh else (
                    e.get("drug") or e.get("药品")
                )
                lines.append(f"• {drug}：监测 {monitor}" if zh else f"• {drug}: monitor {monitor}")
    seen: set[str] = set()
    lines = [ln for ln in lines if not (ln in seen or seen.add(ln))]
    if preg_only:
        hits = [ln for ln in lines if any(w in ln or w in ln.lower() for w in _PREG_WORDS)]
        if hits:
            lines = hits
        else:
            return [
                f"上传的资料文件中未记录「{_name(c, zh)}」治疗的妊娠相关特殊指引。"
                if zh
                else f"The uploaded files do not record pregnancy-specific guidance for "
                f"{_name(c, zh)} treatments."
            ]
    if not lines:
        return []
    head = (
        f"资料文件中「{_name(c, zh)}」治疗的安全信息："
        if zh
        else f"Safety information in the files for {_name(c, zh)} treatments:"
    )
    return [head, *lines[:8]]


def _sec_treatment(c: dict, question: str, lang: str) -> list[str]:
    zh = lang == "zh"
    block = demo_derm._treatment_block({"cond": c}, lang, demo_derm._severity(question))
    if not block:
        return []
    head = (
        f"资料文件中「{_name(c, zh)}」的治疗方案："
        if zh
        else f"Treatment options for {_name(c, zh)} in the uploaded files:"
    )
    lines = [head]
    for m in block.get("medications", [])[:5]:
        ln = f"• {m['drug']} — {m['dose']}" if m.get("dose") else f"• {m['drug']}"
        if m.get("duration"):
            ln += f"，{m['duration']}" if zh else f", {m['duration']}"
        if m.get("note"):
            ln += f"（{m['note']}）" if zh else f" ({m['note']})"
        lines.append(ln)
    for p in block.get("plan", [])[:3]:
        lines.append(f"• {p}")
    if block.get("monitoring"):
        lines.append(f"• 监测：{block['monitoring']}" if zh else f"• Monitoring: {block['monitoring']}")
    return lines if len(lines) > 1 else []


def _sec_differential(
    c: dict, comparator: dict | None, last_reply: dict | None, lang: str
) -> list[str]:
    zh = lang == "zh"
    ddx = c["ddx_zh"] if (zh and c["ddx_zh"]) else c["ddx_en"]
    entries = list(ddx or [])
    if comparator is not None:
        comp_tokens = set(_WORD_RE.findall(comparator["slug"].replace("_", " ")))
        comp_zh = comparator["name_zh"] or ""
        filtered = [
            d
            for d in entries
            if (set(_WORD_RE.findall(str(d.get("disease", "")).replace("_", " "))) & comp_tokens)
            or (comp_zh and comp_zh in str(d.get("疾病", "")))
        ]
        entries = filtered or entries
    lines: list[str] = []
    diff = (last_reply or {}).get("differential") or []
    if diff and (diff[0].get("condition") or "").lower() in (
        c["name_en"].lower(),
        (c["name_zh"] or "").lower(),
    ):
        because = diff[0].get("because") or ""
        if because:
            lines.append(f"• 排名第一：{because}" if zh else f"• Ranked first — {because}")
    for d in entries[:4]:
        if zh and c["ddx_zh"]:
            lines.append(f"• 与{d.get('疾病', '')}鉴别：{d.get('鉴别要点', '')}")
        else:
            disease = str(d.get("disease", "")).replace("_", " ")
            lines.append(f"• vs {disease}: {d.get('differentiator', '')}")
    if not lines:
        return []
    head = (
        f"资料文件中「{_name(c, zh)}」的鉴别要点："
        if zh
        else f"Differentiators for {_name(c, zh)} in the uploaded files:"
    )
    return [head, *lines]


def _sec_tests(c: dict, lang: str) -> list[str]:
    zh = lang == "zh"
    labs = c["labs_zh"] if (zh and c["labs_zh"]) else c["labs_en"]
    if not labs:
        return []
    head = (
        f"资料文件中「{_name(c, zh)}」的检查："
        if zh
        else f"Tests in the uploaded files for {_name(c, zh)}:"
    )
    return [head, *[f"• {str(x).replace('_', ' ')}" for x in labs[:6]]]


def _sec_followup(c: dict, lang: str) -> list[str]:
    zh = lang == "zh"
    follow = c["follow_zh"] if (zh and c["follow_zh"]) else c["follow_en"]
    if not follow:
        return []
    head = f"资料文件中「{_name(c, zh)}」的随访：" if zh else f"Follow-up in the files for {_name(c, zh)}:"
    return [head, *[f"• {str(k).replace('_', ' ')}: {v}" for k, v in list(follow.items())[:4]]]


def _sec_education(c: dict, lang: str) -> list[str]:
    zh = lang == "zh"
    edu = c["edu_zh"] if (zh and c["edu_zh"]) else c["edu_en"]
    if not edu:
        return []
    head = f"资料文件中「{_name(c, zh)}」的患者教育：" if zh else f"Patient education in the files for {_name(c, zh)}:"
    return [head, *[f"• {x}" for x in edu[:4]]]


def _sec_findings(c: dict, lang: str) -> list[str]:
    zh = lang == "zh"
    fs = c["findings_zh"] if (zh and c["findings_zh"]) else c["findings_en"]
    if not fs:
        return []
    head = f"资料文件中「{_name(c, zh)}」的关键体征：" if zh else f"Key findings in the files for {_name(c, zh)}:"
    return [head, *[f"• {str(x).replace('_', ' ')}" for x in fs[:5]]]


def _sec_overview(c: dict, question: str, lang: str) -> list[str]:
    lines = _sec_findings(c, lang)
    tests = _sec_tests(c, lang)
    if tests:
        lines += tests[:2]
    tx = _sec_treatment(c, question, lang)
    if tx:
        lines += tx[:3]
    return lines


@lru_cache
def _drug_ref() -> dict:
    try:
        with open(DRUG_REF_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001 - reference file is optional
        return {}


def _drugref_lines(question: str, lang: str) -> list[str]:
    """Facts about a drug named in the question, from the uploaded drug reference."""
    ref = _drug_ref()
    toks = _q_tokens(question)
    zh = lang == "zh"
    lines: list[str] = []
    for key, info in (ref.get("drugs") or {}).items():
        key_toks = {t for t in _WORD_RE.findall(key.lower()) if len(t) >= 4}
        if not key_toks or not key_toks <= toks:
            continue
        bits: list[str] = []
        classes = info.get("classes") or []
        if classes:
            bits.append(("类别：" if zh else "classes: ") + ", ".join(classes))
        if info.get("max_daily_mg"):
            bits.append(("每日最大剂量 " if zh else "max daily ") + f"{info['max_daily_mg']}mg")
        if info.get("qt_prolonging"):
            bits.append("可延长QT间期" if zh else "QT-prolonging")
        if info.get("cyp3a4_inhibitor"):
            bits.append("CYP3A4抑制剂" if zh else "CYP3A4 inhibitor")
        if info.get("renal_adjust"):
            bits.append("需肾功能调整剂量" if zh else "renal dose adjustment required")
        if bits:
            lines.append(f"• {key}：{'；'.join(bits)}" if zh else f"• {key} — {'; '.join(bits)}")
        names = {key, *classes}
        for it in ref.get("interactions") or []:
            if it.get("a") in names or it.get("b") in names:
                lines.append(f"• {it.get('a')} + {it.get('b')} [{it.get('severity')}]: {it.get('message')}")
        bounds = (ref.get("dosing_bounds") or {}).get(key) or {}
        for note_key in ("geriatric_note", "renal_note", "hepatic_note", "pediatric_note"):
            if bounds.get(note_key):
                lines.append(f"• {key}: {bounds[note_key]}")
    if not lines:
        return []
    head = "来自已上传的药物参考文件：" if zh else "From the uploaded drug reference file:"
    return [head, *lines[:6]]


def answer(question: str, last_reply: dict | None, lang: str) -> str | None:
    """Answer an informational follow-up strictly from the uploaded files.

    Returns None when the files do not contain the requested information — the
    caller then states exactly that. This function never consults an AI model.
    """
    question = (question or "").strip()
    if not question:
        return None

    facets = _facets(question)
    named = _named_conditions(question)
    drugs = _named_drugs(question)
    drugref = _drugref_lines(question, lang)
    if not (facets or named or drugs or drugref):
        return None

    base = named[0] if named else _condition_from_reply(last_reply)
    comparator = next((c for c in named[1:] if c is not base), None)

    sections: list[str] = []
    for m in drugs[:3]:
        sections += _render_drug(m, lang == "zh")

    if base is not None:
        if "differential" in facets:
            sections += _sec_differential(base, comparator, last_reply, lang)
        if "treatment" in facets and not drugs:
            sections += _sec_treatment(base, question, lang)
        if "safety" in facets and not drugs:
            sections += _sec_safety(base, question, lang)
        if "tests" in facets:
            sections += _sec_tests(base, lang)
        if "followup" in facets:
            sections += _sec_followup(base, lang)
        if "education" in facets:
            sections += _sec_education(base, lang)
        if "findings" in facets:
            sections += _sec_findings(base, lang)
        if not sections and named and not facets:
            sections += _sec_overview(base, question, lang)

    sections += drugref

    if not sections:
        return None
    footer = _FOOTER["zh" if lang == "zh" else "en"]
    return "\n".join([*sections[:_MAX_LINES], footer])
