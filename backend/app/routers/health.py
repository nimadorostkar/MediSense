from fastapi import APIRouter

from ..config import get_settings
from ..engine.vector_index import get_index
from ..versions import DRUGREF_VERSION, MODEL_VERSION, RULESET_VERSION

router = APIRouter()


@router.get("/api/health")
async def health() -> dict:
    s = get_settings()
    return {
        "ok": True,
        "episodes": get_index().size,
        "modelVersion": MODEL_VERSION,
        "ruleSetVersion": RULESET_VERSION,
        "drugRefVersion": DRUGREF_VERSION,
        "llmReasoning": bool(s.anthropic_api_key),
        "datastore": "postgres" if s.is_postgres else "sqlite",
    }
