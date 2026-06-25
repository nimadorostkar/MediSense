"""MediSense API — application entrypoint.

Run:  uvicorn app.main:app --reload --port 8787   (from backend/)
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .db import init_db
from .routers import audit, clinical, encounters, episodes, health, triage
from .seed import seed_if_empty

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    n = await seed_if_empty()
    print(f"MediSense engine ready — {n} episodes indexed.")
    yield


app = FastAPI(title="MediSense API", version="2.0-pilot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (health.router, clinical.router, encounters.router,
          episodes.router, triage.router, audit.router):
    app.include_router(r)

# Optionally serve the built frontend (frontend/dist) from the same origin.
_dist = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if _dist.exists():
    app.mount("/", StaticFiles(directory=str(_dist), html=True), name="frontend")
