"""Canonical SQLAlchemy entities (spec §5 / §15).

UUID PKs, created/updated timestamps, soft-delete where clinical. The audit
table is append-only and hash-chained (see security/audit.py).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import (
    Base,
    Embedding,
    GUID,
    created_column,
    pk_column,
    updated_column,
)


class Patient(Base):
    """Demographics & safety context (sourced from EHR via the adapter)."""

    __tablename__ = "patients"

    id: Mapped[str] = pk_column()
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(8), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allergies: Mapped[list] = mapped_column(default=list)
    medications: Mapped[list] = mapped_column(default=list)
    problem_list: Mapped[list] = mapped_column(default=list)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_column()
    updated_at: Mapped[datetime] = updated_column()


class Encounter(Base):
    """One consultation."""

    __tablename__ = "encounters"

    id: Mapped[str] = pk_column()
    patient_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True)
    symptom_text: Mapped[str] = mapped_column(Text, default="")
    vitals: Mapped[dict] = mapped_column(default=dict)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(8), nullable=True)
    allergies: Mapped[list] = mapped_column(default=list)
    medications: Mapped[list] = mapped_column(default=list)
    negatives: Mapped[list] = mapped_column(default=list)
    lang: Mapped[str] = mapped_column(String(4), default="en")
    attending: Mapped[str | None] = mapped_column(String(128), nullable=True)
    chief_complaint: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_column()
    updated_at: Mapped[datetime] = updated_column()


class SymptomSet(Base):
    """Coded symptoms for an encounter."""

    __tablename__ = "symptom_sets"

    id: Mapped[str] = pk_column()
    encounter_id: Mapped[str] = mapped_column(GUID(), ForeignKey("encounters.id"))
    coded: Mapped[list] = mapped_column(default=list)
    onset: Mapped[str | None] = mapped_column(String(64), nullable=True)
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(64), nullable=True)
    laterality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    negatives: Mapped[list] = mapped_column(default=list)
    created_at: Mapped[datetime] = created_column()


class DiagnosisEpisode(Base):
    """Outcome-labelled knowledge-base unit — what the engine learns from."""

    __tablename__ = "diagnosis_episodes"

    id: Mapped[str] = pk_column()
    symptom_text: Mapped[str] = mapped_column(Text, default="")
    diagnosis: Mapped[str] = mapped_column(String(256))
    icd: Mapped[str | None] = mapped_column(String(32), nullable=True)
    treatment: Mapped[dict] = mapped_column(default=dict)
    outcome: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1 recovery signal
    next_best_test: Mapped[str | None] = mapped_column(String(128), nullable=True)
    supporting: Mapped[list] = mapped_column(default=list)
    embedding: Mapped[list | None] = mapped_column(Embedding(), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="seed")
    deidentified: Mapped[bool] = mapped_column(Boolean, default=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = created_column()


class Medication(Base):
    """Current/historical medication for interaction screening."""

    __tablename__ = "medications"

    id: Mapped[str] = pk_column()
    patient_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("patients.id"), nullable=True)
    drug: Mapped[str] = mapped_column(String(128))
    drug_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dose: Mapped[str | None] = mapped_column(String(64), nullable=True)
    route: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = created_column()


class Suggestion(Base):
    """What the engine returned — fully version-stamped (spec §3.5)."""

    __tablename__ = "suggestions"

    id: Mapped[str] = pk_column()
    encounter_id: Mapped[str | None] = mapped_column(
        GUID(), ForeignKey("encounters.id"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(32))  # differential | treatment
    payload: Mapped[dict] = mapped_column(default=dict)
    model_version: Mapped[str] = mapped_column(String(64))
    ruleset_version: Mapped[str] = mapped_column(String(64))
    drugref_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_column()


class Decision(Base):
    """What the physician confirmed — audit record AND training signal."""

    __tablename__ = "decisions"

    id: Mapped[str] = pk_column()
    encounter_id: Mapped[str] = mapped_column(GUID(), ForeignKey("encounters.id"))
    confirmed_diagnosis: Mapped[str] = mapped_column(String(256))
    icd: Mapped[str | None] = mapped_column(String(32), nullable=True)
    overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    physician: Mapped[str] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = created_column()


class Prescription(Base):
    """A treatment/Rx awaiting sign-off and pharmacist verification."""

    __tablename__ = "prescriptions"

    id: Mapped[str] = pk_column()
    encounter_id: Mapped[str] = mapped_column(GUID(), ForeignKey("encounters.id"))
    condition: Mapped[str] = mapped_column(String(256))
    payload: Mapped[dict] = mapped_column(default=dict)  # the screened treatment block
    drugref_version: Mapped[str] = mapped_column(String(64))
    ruleset_version: Mapped[str] = mapped_column(String(64))
    has_hard_block: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    # proposed -> signed -> verified | held ; write-back: pending|written|failed
    signed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    writeback_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = created_column()
    updated_at: Mapped[datetime] = updated_column()


class AcuityScore(Base):
    """Triage band for an encounter."""

    __tablename__ = "acuity_scores"

    id: Mapped[str] = pk_column()
    encounter_id: Mapped[str] = mapped_column(GUID(), ForeignKey("encounters.id"))
    band: Mapped[str] = mapped_column(String(16))  # CRITICAL | URGENT | ROUTINE
    score: Mapped[float] = mapped_column(Float, default=0.0)
    factors: Mapped[dict] = mapped_column(default=dict)
    trend: Mapped[str | None] = mapped_column(String(16), nullable=True)
    created_at: Mapped[datetime] = created_column()


class AuditEvent(Base):
    """Immutable, hash-chained audit trail (spec §1.6 / §18.3)."""

    __tablename__ = "audit_events"

    id: Mapped[str] = pk_column()
    seq: Mapped[int] = mapped_column(Integer, autoincrement=True, unique=True, index=True)
    actor: Mapped[str] = mapped_column(String(128))
    role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    detail: Mapped[dict] = mapped_column(default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64), default="")
    hash: Mapped[str] = mapped_column(String(64), default="")
    ts: Mapped[datetime] = created_column()


class OutcomeRecord(Base):
    """Structured recovery signal attached to an encounter/episode."""

    __tablename__ = "outcome_records"

    id: Mapped[str] = pk_column()
    encounter_id: Mapped[str] = mapped_column(GUID(), ForeignKey("encounters.id"))
    scale: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1 recovery
    readmission_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_up_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = created_column()


class IdempotencyKey(Base):
    """Stored result for a write idempotency key so retries are safe (spec §4.3)."""

    __tablename__ = "idempotency_keys"

    id: Mapped[str] = pk_column()
    key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    endpoint: Mapped[str] = mapped_column(String(128))
    response: Mapped[dict] = mapped_column(default=dict)
    created_at: Mapped[datetime] = created_column()


class ReviewItem(Base):
    """Active-learning queue: overrides + high-uncertainty/OOD cases (spec §13.3)."""

    __tablename__ = "review_items"

    id: Mapped[str] = pk_column()
    encounter_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    reason: Mapped[str] = mapped_column(String(64))  # override | ood | low_confidence
    priority: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[dict] = mapped_column(default=dict)
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = created_column()
