"""Pydantic v2 request/response contracts (spec §4).

Two surfaces:
- v1 chat (`/api/clinical`): probability is 0–100, returned as a JSON *string*
  inside `{ "text": ... }` exactly as the existing React UI parses it.
- v2 structured (`/v2/...`): probability is 0–1.

camelCase aliases are used on the wire (the frontend is TypeScript) while the
Python attributes stay snake_case.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Band = Literal["High", "Moderate", "Low", "Watch"]
Severity = Literal["Contraindicated", "Major", "Moderate", "Minor"]
Lang = Literal["en", "zh"]


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


# ─────────────────────────────────────────────────────────────────────────────
# v1 chat surface
# ─────────────────────────────────────────────────────────────────────────────
class ChatMessage(BaseModel):
    role: str  # "doctor" | "ai"
    text: str | None = ""


class ClinicalRequest(BaseModel):
    """Accepts the new `{messages, lang}` and legacy `{prompt, lang}` bodies."""

    messages: list[ChatMessage] | None = None
    prompt: str | None = None
    lang: Lang = "en"


class ClinicalResponse(BaseModel):
    """The UI reads `text` and JSON-parses it into a Diagnosis (+ treatment)."""

    text: str


# The structured object that `text` serializes to (probability 0–100):
class DiffItem(CamelModel):
    condition: str
    icd: str = ""
    probability: float  # 0–100 on this surface
    confidence: Band
    because: str = ""


class MedicationItem(CamelModel):
    drug: str
    dose: str | None = ""
    route: str | None = ""
    frequency: str | None = ""
    duration: str | None = ""
    note: str | None = ""


class SafetyFlag(CamelModel):
    severity: Severity
    message: str


class TreatmentBlock(CamelModel):
    best_diagnosis: str = Field(alias="bestDiagnosis")
    icd: str | None = ""
    rationale: str | None = ""
    plan: list[str] = Field(default_factory=list)
    medications: list[MedicationItem] = Field(default_factory=list)
    safety: list[SafetyFlag] = Field(default_factory=list)
    monitoring: str | None = ""
    requires_physician_confirmation: bool = Field(
        default=True, alias="requiresPhysicianConfirmation"
    )


class DiagnosisReply(CamelModel):
    """Serialized into the `text` string of ClinicalResponse."""

    red_flag: str = Field(default="", alias="redFlag")
    summary: str = ""
    differential: list[DiffItem] = Field(default_factory=list)
    next_best_test: str = Field(default="", alias="nextBestTest")
    treatment: TreatmentBlock | None = None
    model_version: str = Field(alias="modelVersion")
    rule_set_version: str = Field(alias="ruleSetVersion")
    requires_physician_confirmation: bool = Field(
        default=True, alias="requiresPhysicianConfirmation"
    )
    degraded_mode: bool = Field(default=False, alias="degradedMode")
    ood: bool = False


class HealthResponse(BaseModel):
    ok: bool
    episodes: int
    modelVersion: str
    ruleSetVersion: str
    drugRefVersion: str
    llmReasoning: bool
    datastore: str


# ─────────────────────────────────────────────────────────────────────────────
# v2 structured surface (probability 0–1)
# ─────────────────────────────────────────────────────────────────────────────
class SymptomSubmission(CamelModel):
    symptom_text: str = Field(alias="symptomText")
    age: int | None = None
    sex: str | None = None
    vitals: dict[str, Any] = Field(default_factory=dict)
    allergies: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    negatives: list[str] = Field(default_factory=list)
    lang: Lang = "en"


class V2DiffItem(CamelModel):
    condition: str
    icd: str = ""
    probability: float  # 0–1 here
    confidence: Band
    supporting: list[str] = Field(default_factory=list)
    contradicting: list[str] = Field(default_factory=list)
    similar_cases: int = Field(default=0, alias="similarCases")
    typical_outcomes: dict[str, float] = Field(default_factory=dict, alias="typicalOutcomes")
    next_best_test: str = Field(default="", alias="nextBestTest")
    counterfactual: dict[str, Any] | None = None


class DifferentialResponse(CamelModel):
    encounter_id: str = Field(alias="encounterId")
    differential: list[V2DiffItem] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list, alias="redFlags")
    ood: bool = False
    model_version: str = Field(alias="modelVersion")
    rule_set_version: str = Field(alias="ruleSetVersion")
    requires_physician_confirmation: bool = Field(
        default=True, alias="requiresPhysicianConfirmation"
    )
    degraded_mode: bool = Field(default=False, alias="degradedMode")


class DiagnosisConfirmation(CamelModel):
    condition: str
    icd: str | None = ""
    overridden: bool = False
    override_reason: str | None = Field(default=None, alias="overrideReason")
    physician: str


class PrescriptionRequest(CamelModel):
    condition: str
    allergies: list[str] = Field(default_factory=list)
    current_medications: list[str] = Field(default_factory=list, alias="currentMedications")
    age: int | None = None
    vitals: dict[str, Any] = Field(default_factory=dict)
    lang: Lang = "en"


class PrescriptionResponse(CamelModel):
    encounter_id: str = Field(alias="encounterId")
    prescription_id: str | None = Field(default=None, alias="prescriptionId")
    drug_ref_version: str = Field(alias="drugRefVersion")
    rule_set_version: str = Field(alias="ruleSetVersion")
    treatment: TreatmentBlock


class SignRequest(CamelModel):
    physician: str
    override_reason: str | None = Field(default=None, alias="overrideReason")


class VerifyRequest(CamelModel):
    pharmacist: str
    action: Literal["verify", "hold"] = "verify"
    note: str | None = None


class EpisodeIn(CamelModel):
    symptom_text: str = Field(alias="symptomText")
    diagnosis: str
    icd: str | None = ""
    treatment: dict[str, Any] = Field(default_factory=dict)
    outcome: float = 0.0
    next_best_test: str = Field(default="", alias="nextBestTest")
    supporting: list[str] = Field(default_factory=list)


class OutcomeIn(CamelModel):
    scale: float = 0.0
    readmission_flag: bool = Field(default=False, alias="readmissionFlag")
    follow_up_status: str | None = Field(default=None, alias="followUpStatus")
