"""/v2/prescriptions/{id}/sign|verify (spec §4.2, §7.2).

Sign is physician-only and triggers idempotent HIS write-back. A contraindication
hard-block cannot be signed without a typed override reason (logged + surfaced to
the pharmacist). Verify/hold is pharmacist-only.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.deps import SessionDep, require
from app.errors import NotFoundError, SafetyBlockError
from app.idempotency import remember, replay
from app.integration.fhir import write_back_prescription
from app.models import Prescription
from app.observability.metrics import CONTRA_OVERRIDES
from app.schemas import SignRequest, VerifyRequest
from app.security.audit import record_event
from app.security.rbac import Permission

router = APIRouter(prefix="/v2", tags=["prescriptions"])


async def _get_rx(session, rx_id: str) -> Prescription:
    rx = await session.get(Prescription, rx_id)
    if rx is None:
        raise NotFoundError("prescription")
    return rx


@router.post("/prescriptions/{rx_id}/sign")
async def sign_prescription(
    rx_id: str,
    body: SignRequest,
    session: SessionDep,
    user: Annotated[object, Depends(require(Permission.SIGN_RX))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict:
    endpoint = f"sign:{rx_id}"
    if (cached := await replay(session, idempotency_key, endpoint)) is not None:
        return cached

    rx = await _get_rx(session, rx_id)

    # Hard safety contract: a contraindication block requires a typed override.
    if rx.has_hard_block and not (body.override_reason and body.override_reason.strip()):
        await record_event(
            session,
            actor=body.physician,
            role=getattr(user, "role", None),
            action="prescription.sign.blocked",
            target=f"prescription:{rx_id}",
            detail={"reason": "contraindication hard block without override"},
        )
        await session.commit()
        raise SafetyBlockError(
            "Prescription has a contraindication — a typed override reason is required to sign.",
            detail={"prescriptionId": rx_id},
        )

    rx.signed_by = body.physician
    rx.override_reason = body.override_reason
    rx.status = "signed"
    rx.writeback_status = await write_back_prescription(rx)

    if rx.has_hard_block and body.override_reason:
        CONTRA_OVERRIDES.inc()
        await record_event(
            session,
            actor=body.physician,
            role=getattr(user, "role", None),
            action="safety.override",
            target=f"prescription:{rx_id}",
            detail={"overrideReason": body.override_reason, "surfacedToPharmacist": True},
        )

    await record_event(
        session,
        actor=body.physician,
        role=getattr(user, "role", None),
        action="prescription.sign",
        target=f"prescription:{rx_id}",
        detail={"writeback": rx.writeback_status, "condition": rx.condition},
    )
    result = {
        "prescriptionId": rx_id,
        "signed": True,
        "writeback": rx.writeback_status,
        "requiresPhysicianConfirmation": False,  # the sign IS the confirmation
    }
    await remember(session, idempotency_key, endpoint, result)
    await session.commit()
    return result


@router.post("/prescriptions/{rx_id}/verify")
async def verify_prescription(
    rx_id: str,
    body: VerifyRequest,
    session: SessionDep,
    user: Annotated[object, Depends(require(Permission.VERIFY_RX))],
) -> dict:
    rx = await _get_rx(session, rx_id)
    rx.verified_by = body.pharmacist
    rx.status = "verified" if body.action == "verify" else "held"
    await record_event(
        session,
        actor=body.pharmacist,
        role=getattr(user, "role", None),
        action=f"prescription.{body.action}",
        target=f"prescription:{rx_id}",
        detail={"note": body.note, "overrideReasonOnRecord": rx.override_reason},
    )
    await session.commit()
    return {"prescriptionId": rx_id, "status": rx.status}
