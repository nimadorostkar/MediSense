"""Integration tests — learning loop, decision logging, audit hash-chain
integrity and tamper-evidence (spec §11, §13)."""

from __future__ import annotations

import sqlite3

import pytest

from app.db.session import SessionLocal
from app.security.audit import record_event, verify_chain

pytestmark = pytest.mark.asyncio


async def test_episode_capture_embed_index_retrievable(client, physician_headers, nurse_headers):
    # A novel condition not in the seed KB.
    novel = "Kawasaki disease"
    r = await client.post(
        "/v2/episodes",
        headers=physician_headers,
        json={
            "symptomText": "4yo child five days high fever, red eyes, strawberry tongue, "
            "rash, swollen hands",
            "diagnosis": novel,
            "icd": "M30.3",
            "outcome": 0.9,
            "treatment": {"plan": ["IVIG", "high-dose aspirin"], "medications": []},
            "nextBestTest": "Echocardiogram",
        },
    )
    assert r.status_code == 200 and r.json()["indexed"] is True

    # It should now be retrievable on a similar new presentation.
    eid = "enc-kawasaki"
    await client.put(
        f"/v2/encounters/{eid}/symptoms",
        headers=physician_headers,
        json={
            "symptomText": "5yo five days fever, red eyes, strawberry tongue, rash, swollen hands",
            "age": 5,
            "sex": "M",
        },
    )
    diff = await client.get(f"/v2/encounters/{eid}/differential", headers=nurse_headers)
    conditions = {d["condition"] for d in diff.json()["differential"]}
    assert novel in conditions


async def test_diagnosis_logs_decision_and_audit(client, physician_headers, admin_headers):
    eid = "enc-decision"
    await client.put(
        f"/v2/encounters/{eid}/symptoms",
        headers=physician_headers,
        json={"symptomText": "24yo asthmatic wheeze breathless", "age": 24, "sex": "M"},
    )
    await client.post(
        f"/v2/encounters/{eid}/diagnosis",
        headers=physician_headers,
        json={
            "condition": "Acute asthma exacerbation",
            "icd": "J45.901",
            "overridden": True,
            "overrideReason": "clinical gestalt",
            "physician": "Dr Lin",
        },
    )
    events = (await client.get("/v2/audit/events", headers=admin_headers)).json()["events"]
    actions = {e["action"] for e in events}
    assert "diagnosis.confirm" in actions


async def test_idempotent_diagnosis(client, physician_headers):
    eid = "enc-idem"
    await client.put(
        f"/v2/encounters/{eid}/symptoms",
        headers=physician_headers,
        json={"symptomText": "24yo asthmatic wheeze", "age": 24, "sex": "M"},
    )
    h = {**physician_headers, "Idempotency-Key": "k-1"}
    r1 = await client.post(
        f"/v2/encounters/{eid}/diagnosis",
        headers=h,
        json={"condition": "Acute asthma exacerbation", "physician": "Dr Lin"},
    )
    r2 = await client.post(
        f"/v2/encounters/{eid}/diagnosis",
        headers=h,
        json={"condition": "Something else", "physician": "Dr Lin"},
    )
    assert r1.json()["decisionId"] == r2.json()["decisionId"]


async def test_audit_chain_verifies_and_is_tamper_evident(client, physician_headers, admin_headers):
    # Generate a few events.
    eid = "enc-chain"
    await client.put(
        f"/v2/encounters/{eid}/symptoms",
        headers=physician_headers,
        json={"symptomText": "fever cough", "age": 40, "sex": "M"},
    )
    await client.post(
        f"/v2/encounters/{eid}/diagnosis",
        headers=physician_headers,
        json={"condition": "Community-acquired pneumonia", "physician": "Dr Lin"},
    )
    body = (await client.get("/v2/audit/events", headers=admin_headers)).json()
    assert body["chainValid"] is True

    # Tamper directly in the DB and confirm detection.
    conn = sqlite3.connect("./test_medisense.db")
    conn.execute("UPDATE audit_events SET detail='{\"tampered\":true}' WHERE seq=1")
    conn.commit()
    conn.close()
    async with SessionLocal() as s:
        ok, broken = await verify_chain(s)
    assert ok is False and broken == 1


async def test_hash_chain_links_prev_hash():
    async with SessionLocal() as s:
        e1 = await record_event(s, actor="a", action="x")
        e2 = await record_event(s, actor="b", action="y")
        await s.commit()
        assert e2.prev_hash == e1.hash
        assert e1.seq + 1 == e2.seq
