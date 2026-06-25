"""Patient-context enrichment (spec §6.1 step 2).

Best-effort parse of age/sex/vitals/allergies/medications/negatives from the
doctor's free text. Structured fields, when supplied, always take precedence
(the caller overlays them). Missing critical context is surfaced, not invented.
"""

from __future__ import annotations

import re

from app.engine.drug_safety import _ref

_AGE_SEX = re.compile(r"\b(\d{1,3})\s*[-]?\s*(?:y(?:o|rs?|ears?)?\s*)?(?:[-/ ]?\s*)?([mf])\b", re.I)
_AGE_ONLY = re.compile(r"\b(\d{1,3})\s*(?:yo|y/o|years?\s*old|year[- ]old)\b", re.I)
_VITALS = {
    "spo2": re.compile(r"\bspo2\s*[:=]?\s*(\d{2,3})\b", re.I),
    "hr": re.compile(r"\b(?:hr|heart rate|pulse)\s*[:=]?\s*(\d{2,3})\b", re.I),
    "rr": re.compile(r"\b(?:rr|resp(?:iratory)? rate)\s*[:=]?\s*(\d{1,2})\b", re.I),
    "temp": re.compile(r"\b(?:temp|temperature|t)\s*[:=]?\s*(\d{2}(?:\.\d)?)\b", re.I),
    "egfr": re.compile(r"\begfr\s*[:=]?\s*(\d{1,3})\b", re.I),
}
_BP = re.compile(r"\b(?:bp\s*[:=]?\s*)?(\d{2,3})\s*/\s*(\d{2,3})\b", re.I)
_FEVER_TEMP = re.compile(r"\bfever\s*(\d{2}(?:\.\d)?)\b", re.I)
_ALLERGY_PATTERNS = [
    re.compile(r"allerg(?:y|ic)\s*(?:to|:)?\s*([a-z][a-z\- ]+?)(?:[.,;\n]|\band\b|$)", re.I | re.M),
    re.compile(r"\b([a-z][a-z\-]+)\s+allerg", re.I),
]
_NEGATION = re.compile(
    r"\b(?:no|denies|without|negative for|absent)\s+([a-z][a-z\- ]{2,30}?)(?:[.,;\n]|\band\b|$)",
    re.I | re.M,
)
_MED_CONTEXT = re.compile(r"\b(?:on|taking|takes|current meds?|medications?)\s*[:]?\s*([a-z0-9][a-z0-9\-, and]+)", re.I)


def parse_vitals(text: str) -> dict:
    vitals: dict[str, float] = {}
    for key, rx in _VITALS.items():
        m = rx.search(text)
        if m:
            vitals[key] = float(m.group(1))
    bp = _BP.search(text)
    if bp:
        sys_, dia = int(bp.group(1)), int(bp.group(2))
        if sys_ > dia and 40 < sys_ < 300:  # plausibility guard vs. ratios/dates
            vitals["bp_sys"], vitals["bp_dia"] = float(sys_), float(dia)
    if "temp" not in vitals:
        fm = _FEVER_TEMP.search(text)
        if fm:
            vitals["temp"] = float(fm.group(1))
    return vitals


def parse_age_sex(text: str) -> tuple[int | None, str | None]:
    age: int | None = None
    sex: str | None = None
    m = _AGE_SEX.search(text)
    if m:
        age = int(m.group(1))
        sex = m.group(2).upper()
    else:
        a = _AGE_ONLY.search(text)
        if a:
            age = int(a.group(1))
    if sex is None:
        low = text.lower()
        if re.search(r"\b(female|woman|girl|女)\b", low):
            sex = "F"
        elif re.search(r"\b(male|man|boy|男)\b", low):
            sex = "M"
    if age is not None and (age < 0 or age > 120):
        age = None
    return age, sex


def parse_allergies(text: str) -> list[str]:
    found: list[str] = []
    for rx in _ALLERGY_PATTERNS:
        for m in rx.finditer(text):
            token = m.group(1).strip().lower()
            token = re.sub(r"\b(no known|nkda|drug|medication)\b", "", token).strip()
            if token and token not in found and len(token) < 25:
                found.append(token)
    return found


def parse_medications(text: str) -> list[str]:
    meds: set[str] = set()
    known = _ref()["drugs"].keys()
    low = text.lower()
    for drug in known:
        if re.search(rf"\b{re.escape(drug)}\b", low):
            meds.add(drug)
    m = _MED_CONTEXT.search(text)
    if m:
        for part in re.split(r"[,\s]+and\s+|,", m.group(1)):
            p = part.strip().lower()
            if p in known:
                meds.add(p)
    return sorted(meds)


def parse_negatives(text: str) -> list[str]:
    negs: list[str] = []
    for m in _NEGATION.finditer(text):
        term = m.group(1).strip().lower()
        if term and term not in negs and len(term) < 30:
            negs.append(term)
    return negs


def enrich(text: str, overrides: dict | None = None) -> dict:
    """Build the patient context dict the pipeline consumes."""
    overrides = overrides or {}
    age, sex = parse_age_sex(text)
    vitals = parse_vitals(text)
    patient = {
        "text": text,
        "age": age,
        "sex": sex,
        "vitals": vitals,
        "allergies": parse_allergies(text),
        "medications": parse_medications(text),
        "negatives": parse_negatives(text),
        "lang": overrides.get("lang", "en"),
    }
    # Structured fields win over parsed ones (spec §6.1).
    for key in ("age", "sex", "allergies", "medications", "negatives"):
        v = overrides.get(key)
        if v:
            patient[key] = v
    if overrides.get("vitals"):
        patient["vitals"] = {**vitals, **overrides["vitals"]}
    return patient
