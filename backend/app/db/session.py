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
