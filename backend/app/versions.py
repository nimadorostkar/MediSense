"""Version stamps. Every suggestion payload carries these (spec §17.2).

In production these are emitted by the MLOps pipeline (§14.2). Here they are
constants so every response is traceable to a model + rule set + drug reference.
"""

MODEL_VERSION = "dx-2026.06.1-pilot"
RULESET_VERSION = "rules-2026.06.1"
DRUGREF_VERSION = "drugref-2026.06.1"
EMBEDDING_VERSION = "emb-hash-v1"
