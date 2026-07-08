"""Async SQLAlchemy engine + session factory (spec §2: async SQLAlchemy 2.0)."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

# SQLite needs check_same_thread off for the async pool; Postgres ignores it.
_connect_args = {"check_same_thread": False} if settings.is_sqlite else {}

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=not settings.is_sqlite,
    connect_args=_connect_args,
)

SessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding a transactional session."""
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def ensure_pgvector(session: AsyncSession) -> bool:
    """Best-effort `CREATE EXTENSION vector`. Returns True if pgvector is usable."""
    if settings.is_sqlite:
        return False
    from sqlalchemy import text

    try:
        await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await session.commit()
        return True
    except Exception:  # pragma: no cover - permissions / not installed
        await session.rollback()
        return False


# New bilingual columns on diagnosis_episodes → their SQLite types. `create_all`
# only creates missing *tables*, never adds columns to an existing one, so a dev
# database created before the bilingual change is patched in place here (Postgres
# goes through the Alembic migration instead).
_BILINGUAL_COLUMNS = {
    "symptom_text_zh": "TEXT",
    "diagnosis_zh": "VARCHAR(256)",
    "category": "VARCHAR(64)",
    "treatment_zh": "JSON",
    "next_best_test_zh": "VARCHAR(128)",
    "supporting_zh": "JSON",
}


async def ensure_sqlite_columns(session: AsyncSession) -> list[str]:
    """Add any missing bilingual columns to an existing SQLite dev DB (idempotent).

    Returns the columns added (empty on a fresh DB where create_all already made
    them, or on Postgres where Alembic owns the schema)."""
    if not settings.is_sqlite:
        return []
    from sqlalchemy import text

    existing = {
        row[1]
        for row in (
            await session.execute(text("PRAGMA table_info(diagnosis_episodes)"))
        ).all()
    }
    if not existing:  # table not created yet — create_all will include the columns
        return []
    added: list[str] = []
    for col, sql_type in _BILINGUAL_COLUMNS.items():
        if col not in existing:
            await session.execute(
                text(f"ALTER TABLE diagnosis_episodes ADD COLUMN {col} {sql_type}")
            )
            added.append(col)
    if added:
        await session.commit()
    return added
