"""MediSense FastAPI application.

Boots the app, configures logging/metrics/CORS, mounts routers, and runs the
lifespan that prepares the datastore (create tables on SQLite/dev; pgvector +
seed on first start). Production schema changes go through Alembic, not
create_all (spec §2).
"""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import settings
from app.db.base import Base
from app.db.seed import seed_episodes
from app.db.session import SessionLocal, engine, ensure_pgvector
from app.errors import MediSenseError
from app.observability.logging import configure_logging, correlation_id, get_logger
from app.observability.metrics import REQUEST_LATENCY
from app.routers import audit, clinical, encounters, episodes, outcomes, prescriptions, triage

log = get_logger("medisense.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    # SQLite/dev convenience: create tables. On Postgres, Alembic owns schema,
    # but we still create_all if migrations haven't run so the pilot boots.
    async with engine.begin() as conn:
        if not settings.is_sqlite:
            try:
                await conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
            except Exception:  # pragma: no cover
                pass
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as session:
        await ensure_pgvector(session)
        try:
            loaded = await seed_episodes(session)
            if loaded:
                log.info("startup_seed", extra={"episodes": loaded})
        except Exception as exc:  # noqa: BLE001 - never block startup on seed
            log.warning("seed_failed", extra={"error": str(exc)})

    log.info(
        "startup_complete",
        extra={
            "datastore": settings.datastore_label,
            "llm_reasoning": settings.llm_configured,
            "region": settings.data_region,
        },
    )
    yield
    await engine.dispose()


app = FastAPI(
    title="MediSense — Clinical Decision Support API",
    version=settings.model_version,
    description="Hybrid AI engine: retrieve → classify → calibrate → rules/safety (last). "
    "Human-in-the-loop, fully version-stamped and audited.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Lightweight in-process rate limiter (spec §4.3). A gateway/Redis limiter is
# the production form; this guarantees the behaviour exists out of the box. ────
_RATE_WINDOW = 60.0
_hits: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def context_middleware(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex[:16]
    correlation_id.set(cid)
    client = request.client.host if request.client else "anon"

    # Rate limit (skip docs/metrics/health for usability).
    path = request.url.path
    if not path.startswith(("/docs", "/openapi", "/metrics", "/api/health")):
        now = time.monotonic()
        bucket = _hits[client]
        while bucket and now - bucket[0] > _RATE_WINDOW:
            bucket.popleft()
        if len(bucket) >= settings.rate_limit_per_minute:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {"code": "rate_limited", "message": "Too many requests"},
                    "degradedMode": False,
                },
                headers={"x-correlation-id": cid},
            )
        bucket.append(now)

    start = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - start
    REQUEST_LATENCY.labels(route=request.url.path, method=request.method).observe(elapsed)
    response.headers["x-correlation-id"] = cid
    response.headers["x-model-version"] = settings.model_version
    return response


@app.exception_handler(MediSenseError)
async def medisense_error_handler(request: Request, exc: MediSenseError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {"code": exc.code, "message": exc.message, "detail": exc.detail},
            "degradedMode": exc.degraded,
        },
    )


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Routers
app.include_router(clinical.router)
app.include_router(encounters.router)
app.include_router(prescriptions.router)
app.include_router(episodes.router)
app.include_router(triage.router)
app.include_router(outcomes.router)
app.include_router(audit.router)
