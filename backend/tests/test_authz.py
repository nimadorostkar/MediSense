"""AuthZ tests — RBAC enforced at the API boundary (spec §8)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _open_encounter(client, headers, eid="enc-authz"):
    await client.put(
        f"/v2/encounters/{eid}/symptoms",
        headers=headers,
        json={"symptomText": "24yo asthmatic wheeze breathless", "age": 24, "sex": "M"},
    )
    return eid


async def test_missing_token_is_401(client):
    r = await client.get("/v2/triage/queue")
    assert r.status_code == 401


async def test_nurse_cannot_confirm_diagnosis(client, physician_headers, nurse_headers):
    eid = await _open_encounter(client, physician_headers)
    r = await client.post(
        f"/v2/encounters/{eid}/diagnosis",
        headers=nurse_headers,
        json={"condition": "Acute asthma exacerbation", "physician": "Nurse Zhang"},
    )
    assert r.status_code == 403


async def test_pharmacist_cannot_sign_rx(client, physician_headers, pharmacist_headers):
    eid = await _open_encounter(client, physician_headers)
    rx = await client.post(
        f"/v2/encounters/{eid}/prescription",
        headers=physician_headers,
        json={"condition": "Acute asthma exacerbation"},
    )
    rxid = rx.json()["prescriptionId"]
    r = await client.post(
        f"/v2/prescriptions/{rxid}/sign", headers=pharmacist_headers, json={"physician": "Chen"}
    )
    assert r.status_code == 403


async def test_physician_cannot_verify_rx(client, physician_headers):
    eid = await _open_encounter(client, physician_headers)
    rx = await client.post(
        f"/v2/encounters/{eid}/prescription",
        headers=physician_headers,
        json={"condition": "Acute asthma exacerbation"},
    )
    rxid = rx.json()["prescriptionId"]
    r = await client.post(
        f"/v2/prescriptions/{rxid}/verify",
        headers=physician_headers,
        json={"pharmacist": "x", "action": "verify"},
    )
    assert r.status_code == 403


async def test_audit_export_blocked_for_physician(client, physician_headers):
    r = await client.get("/v2/audit/events", headers=physician_headers)
    assert r.status_code == 403


async def test_audit_export_allowed_for_admin(client, admin_headers):
    r = await client.get("/v2/audit/events", headers=admin_headers)
    assert r.status_code == 200
    assert "chainValid" in r.json()
