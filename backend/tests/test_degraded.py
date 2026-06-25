"""Degraded-mode tests — each row of the §7 fallback table. The pipeline always
answers and hard safety blocks still hold."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def _open(client, headers, eid, **kw):
    body = {"symptomText": "62F fever productive cough pleuritic chest pain", "age": 62, "sex": "F"}
    body.update(kw)
    await client.put(f"/v2/encounters/{eid}/symptoms", headers=headers, json=body)
    return eid


async def test_classifier_offline_still_produces_differential(
    client, physician_headers, nurse_headers
):
    eid = await _open(client, physician_headers, "enc-clf")
    r = await client.get(
        f"/v2/encounters/{eid}/differential?classifier=offline", headers=nurse_headers
    )
    assert r.status_code == 200
    d = r.json()
    assert d["degradedMode"] is True
    assert len(d["differential"]) > 0  # retrieval + rules still answer


async def test_drug_reference_offline_still_blocks_contraindication(client, physician_headers):
    eid = await _open(client, physician_headers, "enc-ref", allergies=["penicillin"])
    r = await client.post(
        f"/v2/encounters/{eid}/prescription?drug_reference=offline",
        headers=physician_headers,
        json={"condition": "Community-acquired pneumonia", "allergies": ["penicillin"]},
    )
    tx = r.json()["treatment"]
    # Reduced coverage flagged, but the contraindication hard block still holds.
    assert any(s["severity"] == "Contraindicated" for s in tx["safety"])
    assert any("reduced coverage" in s["message"].lower() for s in tx["safety"])


async def test_triage_scorer_offline_manual_order(client, physician_headers):
    await _open(client, physician_headers, "enc-tri")
    r = await client.get("/v2/triage/queue?scorer=offline", headers=physician_headers)
    d = r.json()
    assert d["degradedMode"] is True
    assert d["banner"]
    if d["queue"]:
        assert d["queue"][0]["band"] == "UNSCORED"


async def test_reasoner_offline_pipeline_answers(client):
    # No ZHIPU key in tests → reasoner is offline; the deterministic pipeline
    # must still return a complete differential.
    import json

    r = await client.post(
        "/api/clinical",
        json={
            "messages": [
                {"role": "doctor", "text": "35F high fever body aches dry cough headache"}
            ],
            "lang": "en",
        },
    )
    reply = json.loads(r.json()["text"])
    assert reply["differential"]
    assert reply["requiresPhysicianConfirmation"] is True


async def test_sparse_symptoms_asks_rather_than_guesses(client):
    import json

    r = await client.post(
        "/api/clinical", json={"messages": [{"role": "doctor", "text": "pain"}], "lang": "en"}
    )
    reply = json.loads(r.json()["text"])
    # Below the information threshold the engine should not fabricate a ranking.
    assert reply["differential"] == []
