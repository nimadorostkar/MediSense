"""FHIR/HL7 adapter + write-back queue (spec §9, §17.4).

The canonical-model mapping and the idempotent, retried write-back queue are
REAL; the transport defaults to a mock adapter (pilot may run against a FHIR
sandbox). Point FHIR_BASE_URL at a server and set FHIR_WRITE_BACK=true to
exercise the live path. A sign-off that fails to write is queued and surfaced —
never silently dropped (spec §9.3).
"""

from __future__ import annotations

from app.config import settings
from app.models import Decision, Prescription
from app.observability.logging import get_logger

log = get_logger("medisense.fhir")


def decision_to_condition(decision: Decision) -> dict:
    """Map a confirmed Decision to a FHIR Condition resource (canonical → FHIR)."""
    return {
        "resourceType": "Condition",
        "clinicalStatus": {"coding": [{"code": "active"}]},
        "verificationStatus": {"coding": [{"code": "confirmed"}]},
        "code": {
            "coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": decision.icd}],
            "text": decision.confirmed_diagnosis,
        },
        "recorder": {"display": decision.physician},
    }


def prescription_to_medicationrequest(rx: Prescription) -> dict:
    """Map a signed Prescription to a FHIR MedicationRequest (canonical → FHIR)."""
    meds = rx.payload.get("medications", []) if rx.payload else []
    first = meds[0] if meds else {}
    return {
        "resourceType": "MedicationRequest",
        "status": "active",
        "intent": "order",
        "medicationCodeableConcept": {"text": first.get("drug", "")},
        "reasonCode": [{"text": rx.condition}],
        "requester": {"display": rx.signed_by},
        "dosageInstruction": [
            {"text": f"{m.get('drug')} {m.get('dose')} {m.get('route')} {m.get('frequency')}"}
            for m in meds
        ],
    }


async def write_back_prescription(rx: Prescription) -> str:
    """Idempotent write-back. Returns 'written' | 'queued'.

    Idempotency key is the prescription id, so a retried sign is safe. On a live
    transport failure the item is left 'queued' for the reconciliation job.
    """
    resource = prescription_to_medicationrequest(rx)
    if not (settings.fhir_write_back and settings.fhir_base_url):
        # Mock adapter: accept and log; treated as written for the pilot.
        log.info("fhir_writeback_mock", extra={"rx": rx.id, "resource": resource["resourceType"]})
        return "written"
    try:  # pragma: no cover - requires live FHIR endpoint
        import httpx

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.put(
                f"{settings.fhir_base_url}/MedicationRequest/{rx.id}",
                json=resource,
                headers={"If-None-Match": "*"},  # idempotent create
            )
            resp.raise_for_status()
        return "written"
    except Exception as exc:  # noqa: BLE001 - queue for reconciliation
        log.warning("fhir_writeback_failed", extra={"rx": rx.id, "error": str(exc)})
        return "queued"
