"""Vector index (spec §12.4 / §15.3).

Pilot: an in-memory cosine index over episode embeddings — trivial to operate
and ample for thousands of episodes. The `VectorIndex` interface is the seam:
swap `InMemoryVectorIndex` for pgvector or Milvus at scale (§16.3) without
changing the retrieval/classify code that depends on it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Neighbor:
    episode_id: str
    score: float           # cosine similarity, 0..1
    payload: dict          # the episode row (diagnosis, treatment, outcome, ...)


class InMemoryVectorIndex:
    def __init__(self) -> None:
        self._ids: list[str] = []
        self._payloads: list[dict] = []
        self._matrix: np.ndarray | None = None

    def build(self, episodes: list[dict]) -> None:
        """episodes: dicts with keys id, embedding (list[float]), and metadata."""
        self._ids = [e["id"] for e in episodes]
        self._payloads = episodes
        if episodes:
            self._matrix = np.array([e["embedding"] for e in episodes], dtype=np.float32)
        else:
            self._matrix = None

    def search(self, query: np.ndarray, k: int = 8) -> list[Neighbor]:
        if self._matrix is None or len(self._ids) == 0:
            return []
        sims = self._matrix @ query  # rows are already L2-normalized
        k = min(k, len(self._ids))
        top = np.argsort(-sims)[:k]
        return [
            Neighbor(self._ids[i], float(max(0.0, sims[i])), self._payloads[i])
            for i in top
        ]

    @property
    def size(self) -> int:
        return len(self._ids)


_index = InMemoryVectorIndex()


def get_index() -> InMemoryVectorIndex:
    return _index
