"""Embedding service (spec §12.4).

The interface is what matters: swap `HashingEmbedder` for a clinical-domain
encoder (e.g. a fine-tuned sentence-transformer) without touching the rest of
the pipeline. The pilot uses a dependency-free hashing bag-of-words so the slice
runs offline and deterministically.
"""
from __future__ import annotations

import hashlib
import re
from typing import Protocol

import numpy as np

from ..versions import EMBEDDING_VERSION

_DIM = 256
_TOKEN = re.compile(r"[a-z0-9]+")

# Light clinical normalization so synonyms land near each other.
_SYNONYMS = {
    "sob": "dyspnea", "breathless": "dyspnea", "breathlessness": "dyspnea",
    "temperature": "fever", "febrile": "fever", "pyrexia": "fever",
    "bp": "bloodpressure", "hr": "heartrate", "spo2": "oxygen",
    "chestpain": "chest pain", "abdo": "abdominal", "tummy": "abdominal",
    "vomiting": "nausea", "throwing": "nausea", "loose": "diarrhea",
    "headaches": "headache", "migraines": "migraine",
}


def normalize(text: str) -> list[str]:
    toks = _TOKEN.findall((text or "").lower())
    return [_SYNONYMS.get(t, t) for t in toks]


class Embedder(Protocol):
    version: str

    def embed(self, text: str) -> np.ndarray: ...


class HashingEmbedder:
    """Deterministic hashed bag-of-words → L2-normalized vector."""

    version = EMBEDDING_VERSION

    def __init__(self, dim: int = _DIM) -> None:
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim, dtype=np.float32)
        for tok in normalize(text):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            vec[h % self.dim] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 0 else vec


_embedder: Embedder = HashingEmbedder()


def get_embedder() -> Embedder:
    return _embedder
