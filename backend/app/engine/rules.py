"""Clinical rules / safety layer — evaluated LAST, hard veto (spec §6.1, §12.6).

Declarative, versioned, deterministic. Red-flag / do-not-miss conditions are
surfaced and pinned as `Watch` regardless of statistical rank (anti-anchoring),
and critically abnormal vitals raise a banner. This module never lowers safety:
it can only add/raise flags and pin do-not-miss conditions.

The rule set is data, not code branches, so it is auditable and swappable per
site without re-engineering (spec §22.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config import settings
from app.engine.classify import Candidate
from app.engine.embeddings import _tokenize
from app.engine.labels import icd_for
from app.observability.metrics import SAFETY_BLOCKS


@dataclass
class RedFlagRule:
    name: str
    condition: str  # surfaced do-not-miss condition (matches code map)
    any_groups: list[list[str]]  # AND across groups, OR within a group
    priority: int
    banner_en: str
    banner_zh: str
    vitals: dict | None = None  # optional vitals predicate
    sex: str | None = None


# Versioned, expert-curated do-not-miss rule set. Tokens are matched against the
# tokenized free text (so "radiating" matches "radiat" prefix via `startswith`).
RED_FLAG_RULES: list[RedFlagRule] = [
    RedFlagRule(
        "acs",
        "Acute coronary syndrome",
        [
            ["chest"],
            ["pain", "pressure", "tightness", "discomfort"],
            [
                "arm",
                "jaw",
                "diaphoretic",
                "diaphoresis",
                "sweating",
                "sweaty",
                "radiat",
                "exertion",
            ],
        ],
        100,
        "RED FLAG: features of acute coronary syndrome — assess now (ECG + troponin).",
        "红旗警示：符合急性冠脉综合征特征——立即评估（心电图+肌钙蛋白）。",
    ),
    RedFlagRule(
        "stroke",
        "Acute ischaemic stroke",
        [
            ["weakness", "droop", "slurred", "speech", "numbness", "facial"],
            ["sudden", "acute", "onset", "left", "right"],
        ],
        95,
        "RED FLAG: possible stroke — activate stroke pathway, urgent CT head.",
        "红旗警示：疑似脑卒中——启动卒中流程，急查头颅CT。",
    ),
    RedFlagRule(
        "sepsis",
        "Sepsis",
        [["fever", "rigors", "feverish", "hot"]],
        92,
        "RED FLAG: possible sepsis (abnormal vitals) — blood cultures + lactate, sepsis bundle.",
        "红旗警示：疑似脓毒症（生命体征异常）——血培养+乳酸，启动脓毒症集束化治疗。",
        vitals={"any": [("bp_sys", "<", 100), ("hr", ">", 120), ("rr", ">", 24)]},
    ),
    RedFlagRule(
        "pe",
        "Pulmonary embolism",
        [
            ["pleuritic", "chest", "breathless", "dyspnea", "dyspnoea"],
            ["flight", "immobile", "immobility", "calf", "leg", "tachycardia", "swelling", "clot"],
        ],
        88,
        "RED FLAG: consider pulmonary embolism — Wells score / CTPA.",
        "红旗警示：考虑肺栓塞——Wells评分/CT肺动脉造影。",
    ),
    RedFlagRule(
        "dissection",
        "Aortic dissection",
        [["tearing", "ripping", "tear"], ["back", "chest"]],
        90,
        "RED FLAG: tearing pain — exclude aortic dissection (CT angiogram).",
        "红旗警示：撕裂样疼痛——排除主动脉夹层（CT血管造影）。",
    ),
    RedFlagRule(
        "dka",
        "Diabetic ketoacidosis",
        [
            ["polyuria", "polydipsia", "thirst", "ketotic", "fruity", "kussmaul", "glucose"],
            ["breathing", "breath", "vomiting", "abdominal", "weight", "diabetic", "diabetes"],
        ],
        85,
        "RED FLAG: possible DKA — check ketones/glucose/venous gas.",
        "红旗警示：疑似糖尿病酮症酸中毒——查酮体/血糖/静脉血气。",
    ),
    RedFlagRule(
        "ectopic",
        "Ectopic pregnancy",
        [["abdominal", "pelvic", "lower"], ["missed", "amenorrhea", "pregnan", "spotting"]],
        86,
        "RED FLAG: rule out ectopic pregnancy — beta-hCG + transvaginal ultrasound.",
        "红旗警示：排除异位妊娠——β-hCG+经阴道超声。",
        sex="F",
    ),
    RedFlagRule(
        "appendicitis",
        "Acute appendicitis",
        # Require a genuinely abdominal anchor (not bare "right"/"fever") so a
        # right-sided *chest* pain does not false-fire (precision over recall).
        [
            ["abdominal", "rlq", "iliac", "periumbilical", "mcburney"],
            ["rebound", "guarding", "mcburney", "anorexia", "migrat", "quadrant"],
        ],
        80,
        "Possible appendicitis — surgical assessment, imaging.",
        "疑似阑尾炎——外科评估及影像学检查。",
    ),
    RedFlagRule(
        "meningitis",
        "Meningitis",
        [["headache", "head"], ["neck", "stiff", "stiffness", "photophobia", "rash"]],
        91,
        "RED FLAG: features of meningitis — do not delay antibiotics; urgent assessment.",
        "红旗警示：脑膜炎特征——勿延误抗生素；紧急评估。",
        vitals={"any": [("temp", ">", 38.0)]},
    ),
]

RULESET_VERSION = settings.ruleset_version


@dataclass
class RulesResult:
    candidates: list[Candidate]
    red_flags: list[str]
    banner: str = ""
    has_red_flag: bool = False
    matched_rules: list[str] = field(default_factory=list)


def _cmp(value: float, op: str, threshold: float) -> bool:
    return value < threshold if op == "<" else value > threshold


def _vitals_match(pred: dict | None, vitals: dict) -> bool:
    if not pred:
        return True
    checks = pred.get("any", [])
    for key, op, thr in checks:
        v = vitals.get(key)
        if v is not None and _cmp(float(v), op, float(thr)):
            return True
    return False


def _group_match(tokens: set[str], group: list[str]) -> bool:
    for term in group:
        for tok in tokens:
            if tok == term or tok.startswith(term) or term.startswith(tok):
                return True
    return False


def _rule_matches(rule: RedFlagRule, tokens: set[str], vitals: dict, sex: str | None) -> bool:
    if rule.sex and (sex or "").upper() != rule.sex:
        return False
    if not all(_group_match(tokens, g) for g in rule.any_groups):
        return False
    return not (rule.vitals and not _vitals_match(rule.vitals, vitals))


def _abnormal_vitals_banner(vitals: dict, lang: str) -> str | None:
    flags = []
    if (v := vitals.get("spo2")) is not None and v < 92:
        flags.append("低氧血症 (SpO2<92%)" if lang == "zh" else "hypoxia (SpO2<92%)")
    if (v := vitals.get("bp_sys")) is not None and v < 90:
        flags.append("低血压" if lang == "zh" else "hypotension")
    if (v := vitals.get("hr")) is not None and v > 130:
        flags.append("严重心动过速" if lang == "zh" else "severe tachycardia")
    if (v := vitals.get("rr")) is not None and v > 28:
        flags.append("呼吸急促" if lang == "zh" else "tachypnea")
    if not flags:
        return None
    joined = "、".join(flags) if lang == "zh" else ", ".join(flags)
    return (
        f"红旗警示：生命体征危急（{joined}）——立即评估。"
        if lang == "zh"
        else f"RED FLAG: critically abnormal vitals ({joined}) — assess immediately."
    )


def apply_rules(candidates: list[Candidate], patient: dict) -> RulesResult:
    """Evaluate the rule set LAST. Surfaces/pins do-not-miss conditions and
    raises red-flag banners. Deterministic and version-stamped."""
    tokens = set(_tokenize(patient.get("text", "")))
    vitals = patient.get("vitals", {}) or {}
    sex = patient.get("sex")
    lang = patient.get("lang", "en")

    by_condition = {c.condition: c for c in candidates}
    red_flags: list[str] = []
    matched: list[tuple[int, str]] = []  # (priority, banner)
    matched_names: list[str] = []

    for rule in sorted(RED_FLAG_RULES, key=lambda r: r.priority, reverse=True):
        if not _rule_matches(rule, tokens, vitals, sex):
            continue
        matched_names.append(rule.name)
        banner = rule.banner_zh if lang == "zh" else rule.banner_en
        red_flags.append(banner)
        matched.append((rule.priority, banner))
        SAFETY_BLOCKS.labels(category=f"redflag:{rule.name}").inc()

        cand = by_condition.get(rule.condition)
        if cand is None:
            # Surface a do-not-miss condition the statistics missed entirely,
            # pinned at low probability so it is never collapsed (spec §6.3).
            cand = Candidate(
                condition=rule.condition,
                icd=icd_for(rule.condition) or "",
                probability=0.05,
                raw_share=0.0,
                similar_cases=0,
                supporting=[],
                typical_outcomes={},
                next_best_test="",
            )
            candidates.append(cand)
            by_condition[rule.condition] = cand
        cand.pinned_watch = True
        cand.red_flag = True

    # Generic critical-vitals banner even when no specific rule fired.
    vit_banner = _abnormal_vitals_banner(vitals, lang)
    if vit_banner:
        red_flags.append(vit_banner)
        matched.append((99, vit_banner))

    # List order stays by calibrated probability (spec §6.5: a do-not-miss like
    # PE at 9% is listed last with a Watch badge). The red-flag BANNER — not list
    # position — is what surfaces a do-not-miss prominently.
    candidates.sort(key=lambda c: c.probability, reverse=True)

    banner = max(matched, key=lambda m: m[0])[1] if matched else ""
    return RulesResult(
        candidates=candidates,
        red_flags=red_flags,
        banner=banner,
        has_red_flag=bool(matched),
        matched_rules=matched_names,
    )
