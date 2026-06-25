"""Automated data-quality pipeline (spec §13.4).

Every candidate episode passes validation BEFORE it can enter the KB: schema
checks, outlier/label-consistency checks, code-map verification, and
de-identification. Bad data is quarantined (rejected) — never silently admitted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.engine.labels import icd_for

# Minimal de-identification: strip obvious direct identifiers from learning text.
_PHONE = re.compile(r"\b\d{7,}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_MRN = re.compile(r"\b(?:mrn|id)\s*[:#]?\s*\w+\b", re.I)
_NAME_HINT = re.compile(r"\b(?:mr|mrs|ms|dr)\.?\s+[A-Z][a-z]+\b")


@dataclass
class QualityResult:
    ok: bool
    cleaned_text: str
    issues: list[str] = field(default_factory=list)
    deidentified: bool = True


def deidentify(text: str) -> str:
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[id]", text)
    text = _MRN.sub("[mrn]", text)
    text = _NAME_HINT.sub("[name]", text)
    return text


def validate_episode(episode: dict) -> QualityResult:
    issues: list[str] = []
    symptom = (episode.get("symptom_text") or episode.get("symptomText") or "").strip()
    diagnosis = (episode.get("diagnosis") or "").strip()
    icd = (episode.get("icd") or "").strip()
    outcome = episode.get("outcome")

    if len(symptom) < 8:
        issues.append("symptom_text too short")
    if not diagnosis:
        issues.append("missing diagnosis")
    if outcome is None or not (0.0 <= float(outcome) <= 1.0):
        issues.append("outcome must be in [0,1]")

    # Code-map verification: if we know the canonical ICD, it must be consistent.
    expected = icd_for(diagnosis)
    if expected and icd and expected != icd:
        issues.append(f"icd {icd} inconsistent with code map ({expected}) for {diagnosis}")

    cleaned = deidentify(symptom)
    return QualityResult(ok=not issues, cleaned_text=cleaned, issues=issues)
