"""Declarative base + cross-dialect column types.

The same models run on PostgreSQL+pgvector (production) and SQLite (zero-setup
dev). `Embedding` stores a vector natively via pgvector on Postgres and degrades
to JSON on SQLite, where the vector index falls back to in-process cosine.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, mapped_column
from sqlalchemy.types import JSON

EMBEDDING_DIM = 256


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    type_annotation_map = {dict: JSON, list: JSON}


class GUID(TypeDecorator):
    """UUID stored as a 36-char string — portable across SQLite and Postgres."""

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        return None if value is None else str(value)

    def process_result_value(self, value, dialect):  # noqa: ANN001
        return value


class Embedding(TypeDecorator):
    """Vector column: pgvector on Postgres, JSON list[float] elsewhere."""

    impl = JSON
    cache_ok = True

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self.dim = dim
        super().__init__()

    def load_dialect_impl(self, dialect):  # noqa: ANN001
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector

                return dialect.type_descriptor(Vector(self.dim))
            except Exception:  # pragma: no cover - pgvector not installed
                return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        if value is None:
            return None
        vec = list(value)
        if dialect.name == "postgresql":
            return vec  # pgvector accepts a python list
        return json.dumps(vec)  # JSON column on sqlite stores text

    def process_result_value(self, value, dialect):  # noqa: ANN001
        if value is None:
            return None
        if isinstance(value, str):
            return json.loads(value)
        return list(value)


# Convenience column factories (kept consistent across every model).
def pk_column():
    return mapped_column(GUID(), primary_key=True, default=new_uuid)


def created_column():
    return mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


def updated_column():
    return mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )
