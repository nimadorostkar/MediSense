"""bilingual diagnosis episodes (EN + ZH surfaces)

Revision ID: 0002_bilingual_episode
Revises: 0001_initial
Create Date: 2026-07-08

Adds the parallel Chinese columns (and a shared ``category``) to
``diagnosis_episodes`` so a single episode stores both the English canonical
text and its Chinese rendering (spec §15.2). Existing rows keep their English
text; the new columns are nullable and default empty.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_bilingual_episode"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "diagnosis_episodes", sa.Column("symptom_text_zh", sa.Text(), nullable=True)
    )
    op.add_column(
        "diagnosis_episodes", sa.Column("diagnosis_zh", sa.String(length=256), nullable=True)
    )
    op.add_column(
        "diagnosis_episodes", sa.Column("category", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "diagnosis_episodes", sa.Column("treatment_zh", sa.JSON(), nullable=True)
    )
    op.add_column(
        "diagnosis_episodes",
        sa.Column("next_best_test_zh", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "diagnosis_episodes", sa.Column("supporting_zh", sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    for col in (
        "supporting_zh",
        "next_best_test_zh",
        "treatment_zh",
        "category",
        "diagnosis_zh",
        "symptom_text_zh",
    ):
        op.drop_column("diagnosis_episodes", col)
