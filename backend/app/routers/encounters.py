"""Versioned clinical API (spec §17.1) — the structured surface behind the chat.

PUT  /v2/encounters/{id}/symptoms      submit / refine the symptom set
GET  /v2/encounters/{id}/differential  ranked differential with evidence (§17.3)
POST /v2/encounters/{id}/diagnosis     physician confirms (logs a Decision)
POST /v2/encounters/{id}/prescription  screened treatment & drug suggestions
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from .. import audit_util
from ..db import get_session
from ..engine import classify as clf
from ..engine import orchestrator, recommend, rules as rules_mod
from ..models import Decision, Encounter, Suggestion
from ..schemas import (
    DiagnosisConfirmation, DifferentialItemV2, DifferentialResponse,
    PrescriptionRequest, PrescriptionResponse, SymptomSubmission, Treatment,
)
from ..versions import DRUGREF_VERSION, MODEL_VERSION, RULESET_VERSION

router = APIRouter(prefix="/v2/encounters")


async def _get_encounter(session: AsyncSession, encounter_id: str) -> Encounter:
    enc = await session.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(404, "Encounter not found")
    return enc


@router.put("/{encounter_id}/symptoms")
async def submit_symptoms(
    encounter_id: str, body: SymptomSubmission, session: AsyncSession = Depends(get_session)
) -> dict:
    enc = await session.get(Encounter, encounter_id)
    if not enc:
        enc = Encounter(id=encounter_id)
        session.add(enc)
    enc.symptom_text = body.symptomText
    enc.lang = body.lang
    enc.vitals = body.vitals or {}
    await audit_util.record(session, "clinician", "symptoms_submitted", encounter_id,
                            {"len": len(body.symptomText)})
    await session.commit()
    return {"encounterId": enc.id, "ok": True}


@router.get("/{encounter_id}/differential", response_model=DifferentialResponse)
async def get_differential(
    encounter_id: str, session: AsyncSession = Depends(get_session)
) -> DifferentialResponse:
    enc = await _get_encounter(session, encounter_id)
    candidates, ood, rule_hit = orchestrator._diff_candidates(enc.symptom_text)

    items: list[DifferentialItemV2] = []
    present = set()
    for c in candidates[:4]:
        prob = c.probability * (0.85 if ood else 1.0)
        items.append(DifferentialItemV2(
            condition=c.condition, icd=c.icd, probability=round(prob, 3),
            confidence=clf.band_for(prob), similarCases=c.similar_cases,
            typicalOutcomes=c.outcomes, nextBestTest=c.next_best_test,
            supporting=[], contradicting=[],
        ))
        present.add(c.condition.lower())
    for dnm in rule_hit.do_not_miss:
        if dnm["condition"].lower() not in present:
            items.append(DifferentialItemV2(
                condition=dnm["condition"], icd=dnm.get("icd", ""), probability=0.08,
                confidence="Watch", nextBestTest=None,
            ))

    resp = DifferentialResponse(
        encounterId=enc.id, modelVersion=MODEL_VERSION, ruleSetVersion=RULESET_VERSION,
        differential=items, redFlags=[rule_hit.red_flag] if rule_hit.red_flag else [],
        ood=ood, requiresPhysicianConfirmation=True,
    )
    session.add(Suggestion(encounter_id=enc.id, kind="differential",
                           payload=resp.model_dump(), model_version=MODEL_VERSION,
                           ruleset_version=RULESET_VERSION))
    await session.commit()
    return resp


@router.post("/{encounter_id}/diagnosis")
async def confirm_diagnosis(
    encounter_id: str, body: DiagnosisConfirmation, session: AsyncSession = Depends(get_session)
) -> dict:
    enc = await _get_encounter(session, encounter_id)
    session.add(Decision(
        encounter_id=enc.id, confirmed_diagnosis=body.condition, confirmed_icd=body.icd,
        overridden=body.overridden, override_reason=body.overrideReason, physician=body.physician,
    ))
    await audit_util.record(session, body.physician or "clinician", "diagnosis_confirmed",
                            encounter_id, {"condition": body.condition, "overridden": body.overridden})
    await session.commit()
    return {"encounterId": enc.id, "confirmed": body.condition, "logged": True}


@router.post("/{encounter_id}/prescription", response_model=PrescriptionResponse)
async def prescribe(
    encounter_id: str, body: PrescriptionRequest, session: AsyncSession = Depends(get_session)
) -> PrescriptionResponse:
    enc = await _get_encounter(session, encounter_id)
    candidates, _, _ = orchestrator._diff_candidates(enc.symptom_text)
    match = next((c for c in candidates if c.condition.lower() == body.condition.lower()), None)
    treatment_dict = match.treatment if match else {}
    outcomes = match.outcomes if match else {}

    treatment = recommend.build_treatment(
        condition=body.condition, icd=body.icd or (match.icd if match else ""),
        treatment_dict=treatment_dict, outcomes=outcomes,
        allergies=body.allergies, current_meds=body.currentMedications, lang=body.lang,
    )
    session.add(Suggestion(encounter_id=enc.id, kind="prescription", payload=treatment,
                           model_version=MODEL_VERSION, ruleset_version=RULESET_VERSION,
                           drugref_version=DRUGREF_VERSION))
    await audit_util.record(session, "clinician", "prescription_suggested", encounter_id,
                            {"condition": body.condition,
                             "flags": [f["severity"] for f in treatment["safety"]]})
    await session.commit()
    return PrescriptionResponse(encounterId=enc.id, drugRefVersion=DRUGREF_VERSION,
                                ruleSetVersion=RULESET_VERSION, treatment=Treatment(**treatment))
