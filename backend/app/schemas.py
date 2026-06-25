"""Pydantic contracts — the typed API boundary.

Two surfaces share one engine:
  • Chat-compat shapes (DiagnosisReply) consumed by the existing React chat UI
    via POST /api/clinical.
  • Versioned /v2 spec shapes (DifferentialResponse) per spec §17.3.

Pydantic enforces these on the way out, so no malformed clinical payload can
leave the server (spec §17.2).
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Band = Literal["High", "Moderate", "Low", "Watch"]
Severity = Literal["Contraindicated", "Major", "Moderate", "Minor"]


# ── Chat-compat surface (consumed by src/types.ts) ──────────────────────────
class DiffItem(BaseModel):
    condition: str
    icd: str = ""
    probability: float = Field(ge=0, le=100)
    confidence: Band
    because: str = ""


class SafetyFlag(BaseModel):
    severity: Severity
    message: str


class Medication(BaseModel):
    drug: str
    dose: str = ""
    route: str = ""
    frequency: str = ""
    duration: str = ""
    note: str = ""


class Treatment(BaseModel):
    bestDiagnosis: str
    icd: str = ""
    rationale: str = ""
    plan: list[str] = []
    medications: list[Medication] = []
    safety: list[SafetyFlag] = []
    monitoring: str = ""
    requiresPhysicianConfirmation: bool = True


class DiagnosisReply(BaseModel):
    """The object the chat UI parses (src/types.ts Diagnosis + treatment)."""

    redFlag: str = ""
    summary: str = ""
    differential: list[DiffItem] = []
    nextBestTest: str = ""
    treatment: Treatment | None = None
    # Traceability stamps (spec §17.2) — informational for the UI.
    modelVersion: str = ""
    ruleSetVersion: str = ""
    requiresPhysicianConfirmation: bool = True


class ClinicalRequest(BaseModel):
    prompt: str = ""
    lang: Literal["en", "zh"] = "en"


class ClinicalResponse(BaseModel):
    # Mirrors the existing server contract: {text: "<json string>"}.
    text: str


# ── Versioned /v2 surface (spec §17.3) ──────────────────────────────────────
class SymptomSubmission(BaseModel):
    symptomText: str
    age: int | None = None
    sex: str | None = None
    vitals: dict = {}
    allergies: list[str] = []
    medications: list[str] = []
    lang: Literal["en", "zh"] = "en"


class DifferentialItemV2(BaseModel):
    condition: str
    icd: str
    probability: float = Field(ge=0, le=1)
    confidence: Band
    supporting: list[str] = []
    contradicting: list[str] = []
    similarCases: int = 0
    typicalOutcomes: dict = {}
    nextBestTest: str | None = None


class DifferentialResponse(BaseModel):
    encounterId: str
    modelVersion: str
    ruleSetVersion: str
    differential: list[DifferentialItemV2] = []
    redFlags: list[str] = []
    ood: bool = False
    requiresPhysicianConfirmation: bool = True


class DiagnosisConfirmation(BaseModel):
    condition: str
    icd: str | None = None
    overridden: bool = False
    overrideReason: str | None = None
    physician: str | None = None


class PrescriptionRequest(BaseModel):
    condition: str
    icd: str | None = None
    allergies: list[str] = []
    currentMedications: list[str] = []
    lang: Literal["en", "zh"] = "en"


class PrescriptionResponse(BaseModel):
    encounterId: str
    drugRefVersion: str
    ruleSetVersion: str
    treatment: Treatment
