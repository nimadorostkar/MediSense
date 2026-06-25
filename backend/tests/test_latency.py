"""Latency check — differential p95 < 5s on seed data (spec §21).

Method: 20 sequential differential calls over the seeded KB on the test host;
assert the 95th percentile is within budget. Documented in BUILD_REPORT.
"""

from __future__ import annotations

import json
import time

import pytest

pytestmark = pytest.mark.asyncio

CASES = [
    "67M chest pain radiating to left arm, diaphoretic, HR 118 BP 92/60",
    "62F 3 days fever, productive cough, right pleuritic chest pain, RR 22 SpO2 94%",
    "24yo asthmatic, wheeze, breathless, cough, SpO2 93",
    "70M sudden left weakness, facial droop, slurred speech",
    "33F dysuria, urinary frequency, suprapubic discomfort",
]


async def test_differential_p95_under_5s(client):
    timings = []
    for i in range(20):
        text = CASES[i % len(CASES)]
        start = time.perf_counter()
        r = await client.post(
            "/api/clinical", json={"messages": [{"role": "doctor", "text": text}], "lang": "en"}
        )
        timings.append(time.perf_counter() - start)
        assert r.status_code == 200
        assert json.loads(r.json()["text"])["differential"]
    timings.sort()
    p95 = timings[int(len(timings) * 0.95) - 1]
    assert p95 < 5.0, f"p95 {p95:.3f}s exceeds 5s budget"
