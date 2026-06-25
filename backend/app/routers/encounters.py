"""/v2/encounters/* — structured clinical flow (spec §4.2).

probability is 0–1 on this surface. Physician-only diagnosis confirmation and Rx
requests are enforced via RBAC. Degraded modes can be exercised with the
`classifier=offline` / `drug_reference=offline` query flags (spec §7).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query

from app.deps import SessionDep, require
from app.engine import orchestrator
from app.engine.enrich import enrich
from app.errors import NotFoundError
from app.idempotency import remember, replay
from app.learning.active_learning import enqueue_review
from app.models import Decision, Encounter, Prescription, Suggestion
from app.observability.metrics import SUGGESTIONS
from app.schemas import (
    DiagnosisConfirmation,
    DifferentialResponse,
    PrescriptionRequest,
    PrescriptionResponse,
    SymptomSubmission,
    TreatmentBlock,
    V2DiffItem,
)
from app.security.audit import record_event
from app.security.rbac import Permission

router = APIRouter(prefix="/v2", tags=["encounters"])


def _patient_from_encounter(enc: Encounter) -> dict:
    return enrich(
        enc.symptom_text,
        {
            "lang": enc.lang,
            "age": enc.age,
            "sex": enc.sex,
            "allergies": enc.allergies,
            "medications": enc.medications,
            "negatives": enc.negatives,
            "vitals": enc.vitals,
        },
    )


async def _get_encounter(session, encounter_id: str) -> Encounter:
    enc = await session.get(Encounter, encounter_id)
    if enc is None or enc.deleted:
        raise NotFoundError("encounter")
    return enc


@router.put("/encounters/{encounter_id}/symptoms")
async def put_symptoms(
    encounter_id: str,
    body: SymptomSubmission,
    session: SessionDep,
    user: Annotated[object, Depends(require(Permission.CAPTURE_INTAKE))],
) -> dict:
    enc = await session.get(Encounter, encounter_id)
    if enc is None:
        enc = Encounter(id=encounter_id)
        session.add(enc)
    enc.symptom_text = body.symptom_text
    enc.age = body.age
    enc.sex = body.sex
    enc.vitals = body.vitals
    enc.allergies = body.allergies
    enc.medications = body.medications
    enc.negatives = body.negatives
    enc.lang = body.lang
    enc.attending = getattr(user, "name", None)
    enc.status = "open"
    await record_event(
        session,
        actor=getattr(user, "name", "unknown"),
        role=getattr(user, "role", None),
        action="symptoms.submit",
        target=f"encounter:{encounter_id}",
        detail={"chars": len(body.symptom_text)},
    )
    await session.commit()
    return {"encounterId": encounter_id, "ok": True}


@router.get("/encounters/{encounter_id}/differential", response_model=DifferentialResponse)
async def get_differential(
    encounter_id: str,
    session: SessionDep,
    user: Annotated[object, Depends(require(Permission.VIEW_DIFFERENTIAL))],
    classifier: str = Query("online"),
) -> DifferentialResponse:
    enc = await _get_encounter(session, encounter_id)
    patient = _patient_from_encounter(enc)
    outcome = await orchestrator.diagnose(
        session, patient, classifier_online=(classifier != "offline")
    )

    items = [
        V2DiffItem(
            condition=c.condition,
            icd=c.icd,
            probability=round(c.probability, 4),
            confidence=orchestrator.band_for(c.probability, c.pinned_watch),
            supporting=c.supporting,
            contradicting=c.contradicting,
            similarCases=c.similar_cases,
            typicalOutcomes=c.typical_outcomes,
            nextBestTest=c.next_best_test,
            counterfactual=(
                {"remove": c.supporting[0], "newProbability": round(c.probability * 0.6, 2)}
                if c.supporting
                else None
            ),
        )
        for c in outcome.candidates
    ]
    SUGGESTIONS.labels(kind="v2_differential", degraded=str(outcome.degraded_mode)).inc()

    suggestion = Suggestion(
        encounter_id=encounter_id,
        kind="differential",
        payload={"differential": [i.model_dump(by_alias=True) for i in items]},
        model_version=orchestrator.settings.model_version,
        ruleset_version=orchestrator.settings.ruleset_version,
        degraded=outcome.degraded_mode,
    )
    session.add(suggestion)
    await record_event(
        session,
        actor=getattr(user, "name", "unknown"),
        role=getattr(user, "role", None),
        action="differential.view",
        target=f"encounter:{encounter_id}",
        detail={"ood": outcome.ood, "degraded": outcome.degraded_mode},
    )
    # Route OOD / low-confidence cases to active learning (spec §13.3).
    if outcome.ood:
        await enqueue_review(
            session,
            reason="ood",
            encounter_id=encounter_id,
            priority=0.9,
            detail={"reason": outcome.ood_reason},
        )
    await session.commit()

    return DifferentialResponse(
        encounterId=encounter_id,
        differential=items,
        redFlags=outcome.red_flags,
        ood=outcome.ood,
        modelVersion=orchestrator.settings.model_version,
        ruleSetVersion=orchestrator.settings.ruleset_version,
        requiresPhysicianConfirmation=True,
        degradedMode=outcome.degraded_mode,
    )


@router.post("/encounters/{encounter_id}/diagnosis")
async def confirm_diagnosis(
    encounter_id: str,
    body: DiagnosisConfirmation,
    session: SessionDep,
    user: Annotated[object, Depends(require(Permission.CONFIRM_DIAGNOSIS))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    endpoint = f"diagnosis:{encounter_id}"
    if (cached := await replay(session, idempotency_key, endpoint)) is not None:
        return cached

    enc = await _get_encounter(session, encounter_id)
    decision = Decision(
        encounter_id=enc.id,
        confirmed_diagnosis=body.condition,
        icd=body.icd,
        overridden=body.overridden,
        override_reason=body.override_reason,
        physician=body.physician,
        model_version=orchestrator.settings.model_version,
    )
    session.add(decision)
    enc.status = "diagnosed"
    await session.flush()

    await record_event(
        session,
        actor=body.physician,
        role=getattr(user, "role", None),
        action="diagnosis.confirm",
        target=f"encounter:{encounter_id}",
        detail={
            "condition": body.condition,
            "icd": body.icd,
            "overridden": body.overridden,
            "overrideReason": body.override_reason,
        },
    )
    # Physician override = highest-value training signal (spec §13.3).
    if body.overridden:
        await enqueue_review(
            session,
            reason="override",
            encounter_id=encounter_id,
            priority=1.0,
            detail={"condition": body.condition, "reason": body.override_reason},
        )

    result = {
        "encounterId": encounter_id,
        "confirmed": True,
        "logged": True,
        "decisionId": decision.id,
    }
    await remember(session, idempotency_key, endpoint, result)
    await session.commit()
    return result


@router.post("/encounters/{encounter_id}/prescription", response_model=PrescriptionResponse)
async def request_prescription(
    encounter_id: str,
    body: PrescriptionRequest,
    session: SessionDep,
    user: Annotated[object, Depends(require(Permission.REQUEST_RX))],
    drug_reference: str = Query("online"),
) -> PrescriptionResponse:
    enc = await _get_encounter(session, encounter_id)
    patient = enrich(
        enc.symptom_text,
        {
            "lang": body.lang,
            "age": body.age if body.age is not None else enc.age,
            "sex": enc.sex,
            "allergies": body.allergies or enc.allergies,
            "medications": body.current_medications or enc.medications,
            "vitals": body.vitals or enc.vitals,
        },
    )
    treatment = await orchestrator.build_treatment(
        session, body.condition, patient, reference_online=(drug_reference != "offline")
    )

    rx = Prescription(
        encounter_id=enc.id,
        condition=body.condition,
        payload=orchestrator._strip_internal(treatment),
        drugref_version=treatment["_drugref_version"],
        ruleset_version=orchestrator.settings.ruleset_version,
        has_hard_block=treatment["_has_hard_block"],
        status="proposed",
    )
    session.add(rx)
    await session.flush()
    await record_event(
        session,
        actor=getattr(user, "name", "unknown"),
        role=getattr(user, "role", None),
        action="prescription.request",
        target=f"prescription:{rx.id}",
        detail={"condition": body.condition, "hardBlock": rx.has_hard_block},
    )
    SUGGESTIONS.labels(kind="treatment", degraded="False").inc()
    await session.commit()

    return PrescriptionResponse(
        encounterId=encounter_id,
        prescriptionId=rx.id,
        drugRefVersion=rx.drugref_version,
        ruleSetVersion=rx.ruleset_version,
        treatment=TreatmentBlock.model_validate(orchestrator._strip_internal(treatment)),
    )
