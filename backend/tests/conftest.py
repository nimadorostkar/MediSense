"""Shared test fixtures. A fresh seeded SQLite DB per test; an httpx AsyncClient
driven through the app lifespan; and role-scoped dev-token headers.
"""

from __future__ import annotations

import os

# Configure the environment BEFORE importing the app (settings cache at import).
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_medisense.db"
os.environ["DEV_AUTH"] = "true"
os.environ["LLM_REASONING"] = "false"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.seed import seed_episodes  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security.oidc import mint_dev_token  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def fresh_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    async with SessionLocal() as session:
        await seed_episodes(session)
    yield


@pytest_asyncio.fixture
async def client():
    # Drive the app without its lifespan re-seeding (fresh_db already seeded).
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _hdr(role: str, name: str) -> dict:
    return {"Authorization": f"Bearer {mint_dev_token(role[:2], name, role)}"}


@pytest.fixture
def physician_headers():
    return _hdr("physician", "Dr Lin")


@pytest.fixture
def nurse_headers():
    return _hdr("nurse", "Nurse Zhang")


@pytest.fixture
def pharmacist_headers():
    return _hdr("pharmacist", "Pharmacist Chen")


@pytest.fixture
def admin_headers():
    return _hdr("admin", "Director Wang")
