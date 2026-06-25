"""ORM entities — the canonical data model (spec §15.1).

Portable across SQLite (pilot) and PostgreSQL (production). Vectors are stored
as JSON arrays for portability; on PostgreSQL the `embedding` column maps cleanly
to a pgvector column in production (see backend/README.md → "Moving to pgvector").
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _uuid("pat"))
    sex: Mapped[str | None] = mapped_column(String, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allergies: Mapped[list] = mapped_column(JSON, default=list)      # ["penicillin", ...]
    medications: Mapped[list] = mapped_column(JSON, default=list)    # current meds
    problem_list: Mapped[list] = mapped_column(JSON, default=list)   # chronic conditions
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    encounters: Mapped[list["Encounter"]] = relationship(back_populates="patient")


class Encounter(Base):
    __tablename__ = "encounters"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _uuid("enc"))
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.id"), nullable=True)
    presenting_complaint: Mapped[str] = mapped_column(Text, default="")
    symptom_text: Mapped[str] = mapped_column(Text, default="")
    vitals: Mapped[dict] = mapped_column(JSON, default=dict)
    lang: Mapped[str] = mapped_column(String, default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    patient: Mapped[Patient | None] = relationship(back_populates="encounters")
    suggestions: Mapped[list["Suggestion"]] = relationship(back_populates="encounter")
    decisions: Mapped[list["Decision"]] = relationship(back_populates="encounter")


class DiagnosisEpisode(Base):
    """The knowledge-base unit (spec §13.1): symptoms → diagnosis → Rx → outcome."""

    __tablename__ = "diagnosis_episodes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _uuid("epi"))
    symptom_text: Mapped[str] = mapped_column(Text, default="")
    department: Mapped[str | None] = mapped_column(String, nullable=True)
    diagnosis: Mapped[str] = mapped_column(String, default="")
    icd: Mapped[str] = mapped_column(String, default="")
    treatment: Mapped[dict] = mapped_column(JSON, default=dict)   # plan + meds
    outcome: Mapped[float] = mapped_column(Float, default=1.0)    # 0..1 recovery signal
    red_flags: Mapped[list] = mapped_column(JSON, default=list)
    next_best_test: Mapped[str | None] = mapped_column(String, nullable=True)
    embedding: Mapped[list] = mapped_column(JSON, default=list)   # vector (pgvector in prod)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Suggestion(Base):
    """A ranked differential / Rx options payload returned to the clinician."""

    __tablename__ = "suggestions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _uuid("sug"))
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"))
    kind: Mapped[str] = mapped_column(String, default="differential")  # or "prescription"
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    model_version: Mapped[str] = mapped_column(String, default="")
    ruleset_version: Mapped[str] = mapped_column(String, default="")
    drugref_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    encounter: Mapped[Encounter] = relationship(back_populates="suggestions")


class Decision(Base):
    """What the doctor confirmed vs. what was suggested (spec §15.1, doubly valuable)."""

    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _uuid("dec"))
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"))
    suggestion_id: Mapped[str | None] = mapped_column(ForeignKey("suggestions.id"), nullable=True)
    confirmed_diagnosis: Mapped[str] = mapped_column(String, default="")
    confirmed_icd: Mapped[str | None] = mapped_column(String, nullable=True)
    overridden: Mapped[bool] = mapped_column(default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    physician: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    encounter: Mapped[Encounter] = relationship(back_populates="decisions")


class AuditEvent(Base):
    """Immutable, hash-chained audit trail (spec §15.3 / §18.3)."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String, default="system")
    action: Mapped[str] = mapped_column(String, default="")
    target: Mapped[str | None] = mapped_column(String, nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    hash: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
