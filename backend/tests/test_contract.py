"""Contract tests — the exact v1 chat JSON shape and v2 schemas (spec §4) so the
existing React frontend works unchanged."""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.asyncio

V1_KEYS = {
    "redFlag",
    "summary",
    "differential",
    "nextBestTest",
    "treatment",
    "modelVersion",
    "ruleSetVersion",
    "requiresPhysicianConfirmation",
}


async def test_health_shape(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    d = r.json()
    for k in (
        "ok",
        "episodes",
        "modelVersion",
        "ruleSetVersion",
        "drugRefVersion",
        "llmReasoning",
        "datastore",
    ):
        assert k in d
    assert d["episodes"] == 24
    assert d["ok"] is True


async def test_clinical_v1_shape_and_probability_0_100(client):
    r = await client.post(
        "/api/clinical",
        json={
            "messages": [
                {
                    "role": "doctor",
                    "text": "67M chest pain radiating to left arm, diaphoretic, HR 118 BP 92/60",
                }
            ],
            "lang": "en",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"text"}
    reply = json.loads(body["text"])
    assert V1_KEYS.issubset(reply.keys())
    assert reply["requiresPhysicianConfirmation"] is True
    assert reply["modelVersion"] and reply["ruleSetVersion"]
    # Red-flag-first: ACS surfaced for this case.
    assert "coronary" in reply["redFlag"].lower() or any(
        "coronary" in d["condition"].lower() for d in reply["differential"]
    )
    for d in reply["differential"]:
        assert {"condition", "icd", "probability", "confidence", "because"}.issubset(d)
        assert 0 <= d["probability"] <= 100  # 0–100 on the chat surface
        assert d["confidence"] in {"High", "Moderate", "Low", "Watch"}


async def test_legacy_prompt_body_accepted(client):
    r = await client.post(
        "/api/clinical",
        json={
            "prompt": "DOCTOR: 24yo asthmatic, wheeze, breathless, cough",
            "lang": "en",
        },
    )
    assert r.status_code == 200
    reply = json.loads(r.json()["text"])
    assert reply["differential"]


async def test_treatment_block_on_prescriptive_turn(client):
    r = await client.post(
        "/api/clinical",
        json={
            "messages": [
                {
                    "role": "doctor",
                    "text": "62F fever productive cough pleuritic chest pain, "
                    "allergic to penicillin",
                },
                {"role": "doctor", "text": "what should I prescribe?"},
            ],
            "lang": "en",
        },
    )
    reply = json.loads(r.json()["text"])
    tx = reply["treatment"]
    assert tx is not None
    assert {
        "bestDiagnosis",
        "plan",
        "medications",
        "safety",
        "monitoring",
        "requiresPhysicianConfirmation",
    }.issubset(tx)
    assert tx["requiresPhysicianConfirmation"] is True
    # Penicillin allergy → amoxicillin withheld, contraindication surfaced.
    assert any(s["severity"] == "Contraindicated" for s in tx["safety"])
    assert "Amoxicillin" not in {m["drug"] for m in tx["medications"]}


async def test_v2_differential_probability_0_1(client, physician_headers, nurse_headers):
    eid = "enc-contract"
    await client.put(
        f"/v2/encounters/{eid}/symptoms",
        headers=physician_headers,
        json={"symptomText": "24yo asthmatic wheeze breathless cough", "age": 24, "sex": "M"},
    )
    r = await client.get(f"/v2/encounters/{eid}/differential", headers=nurse_headers)
    assert r.status_code == 200
    d = r.json()
    assert {
        "encounterId",
        "differential",
        "redFlags",
        "ood",
        "modelVersion",
        "ruleSetVersion",
        "requiresPhysicianConfirmation",
    }.issubset(d)
    for item in d["differential"]:
        assert 0.0 <= item["probability"] <= 1.0  # 0–1 on v2
        assert {"similarCases", "typicalOutcomes", "supporting", "contradicting"}.issubset(item)


async def test_zh_language_output(client):
    r = await client.post(
        "/api/clinical",
        json={
            "messages": [
                {"role": "doctor", "text": "67M chest pain radiating to left arm, diaphoretic"}
            ],
            "lang": "zh",
        },
    )
    reply = json.loads(r.json()["text"])
    # Chinese condition label + ICD preserved.
    assert any("一" <= ch <= "鿿" for ch in reply["summary"])
