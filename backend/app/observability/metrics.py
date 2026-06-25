"""Prometheus metrics (spec §23.1). Exposed at /metrics."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

REQUEST_LATENCY = Histogram(
    "medisense_request_seconds",
    "Request latency by route",
    ["route", "method"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
DIFFERENTIAL_LATENCY = Histogram(
    "medisense_differential_seconds",
    "Differential engine latency (spec §21 budget: p95 < 5s)",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
SUGGESTIONS = Counter("medisense_suggestions_total", "Suggestions emitted", ["kind", "degraded"])
SAFETY_BLOCKS = Counter(
    "medisense_safety_blocks_total", "Hard safety blocks raised", ["category"]
)
CONTRA_OVERRIDES = Counter(
    "medisense_contraindication_overrides_total",
    "Contraindication overrides (clinical-safety signal)",
)
DEGRADED_MODE = Counter("medisense_degraded_mode_total", "Degraded-mode responses", ["component"])
