"""Dermatology knowledge-base loader (bilingual, spec §6.3 / §15.2).

Reads the two site-supplied dermatology core-data files —
``dermatology_core_data_EN.json`` and ``dermatology_core_data_CN.json`` — and
folds each condition into a single bilingual :class:`DiagnosisEpisode`. The two
files describe the *same* 25 conditions in the same order; this loader pairs
them positionally and stores the English text in the canonical columns and the
Chinese text in the parallel ``*_zh`` columns, so one episode holds both
languages and a request's ``lang`` picks the surface to return.

Idempotent: skips if dermatology episodes (``source="derm"``) already exist, so
it is safe to run on every startup alongside the general seed.
"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.engine.embeddings import embed_texts
from app.models import DiagnosisEpisode
from app.observability.logging import get_logger

log = get_logger("medisense.derm")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
EN_FILE = DATA_DIR / "dermatology_core_data_EN.json"
CN_FILE = DATA_DIR / "dermatology_core_data_CN.json"

_SOURCE = "derm"
_SNAPSHOT = "derm-kb-1.0.0"
_DERM_LOCK_KEY = 727275  # distinct from the general-seed advisory lock
# Guideline reference data is not outcome-labelled; use a neutral prior so it
# ranks below real outcome-weighted episodes but is still retrievable.
_DEFAULT_OUTCOME = 0.7


def _join(values: list | None) -> str:
    return ", ".join(str(v) for v in values if v) if values else ""


def _clean_template(tmpl: str | None) -> str:
    """Turn a chief-complaint template into readable prose (drop {placeholders})."""
    if not tmpl:
        return ""
    return " ".join(tmpl.replace("{", "").replace("}", "").replace("_", " ").split())


def _norm_meds_en(prescriptions: dict) -> tuple[list[str], list[dict]]:
    """Flatten the English prescription tiers into (plan, medications)."""
    plan: list[str] = []
    meds: list[dict] = []
    for tier, entries in (prescriptions or {}).items():
        tier_label = tier.replace("_", " ")
        for entry in entries:
            drug = entry.get("drug")
            note = _join(
                [
                    entry.get("special"),
                    ("alert: " + entry["alert"]) if entry.get("alert") else "",
                    ("monitor: " + entry["monitor"]) if entry.get("monitor") else "",
                    ("contraindicated: " + _join(entry.get("contra")))
                    if entry.get("contra")
                    else "",
                ]
            )
            if drug:
                meds.append(
                    {
                        "drug": drug,
                        "dose": entry.get("dose", ""),
                        "route": "",
                        "frequency": "",
                        "duration": entry.get("duration", ""),
                        "note": f"[{tier_label}] {note}".strip(),
                        "insurance": entry.get("insurance", ""),
                    }
                )
            elif entry.get("special"):
                plan.append(f"{tier_label}: {entry['special']}")
    return plan, meds


def _norm_meds_cn(prescriptions: dict) -> tuple[list[str], list[dict]]:
    """Flatten the Chinese prescription tiers into (plan, medications)."""
    plan: list[str] = []
    meds: list[dict] = []
    for tier, entries in (prescriptions or {}).items():
        for entry in entries:
            drug = entry.get("药品") or entry.get("治疗")
            note = _join(
                [
                    entry.get("特殊说明"),
                    ("警示: " + entry["警示"]) if entry.get("警示") else "",
                    ("监测: " + entry["监测"]) if entry.get("监测") else "",
                    ("禁忌: " + _join(entry.get("禁忌"))) if entry.get("禁忌") else "",
                ]
            )
            if drug:
                meds.append(
                    {
                        "drug": drug,
                        "dose": entry.get("用法", ""),
                        "route": "",
                        "frequency": "",
                        "duration": entry.get("疗程", ""),
                        "note": f"[{tier}] {note}".strip(),
                        "insurance": entry.get("医保", ""),
                    }
                )
            elif entry.get("特殊"):
                plan.append(f"{tier}: {entry['特殊']}")
    return plan, meds


def _build_episode(en: dict, cn: dict) -> dict | None:
    """Fold an aligned EN/CN condition pair into one bilingual episode dict.

    Returns None for reference mnemonics (no prescriptions) that are not
    retrievable diagnoses (e.g. the ABCDE rule).
    """
    if not en.get("prescriptions"):
        return None

    diagnosis = en.get("name", "")
    diagnosis_zh = en.get("name_cn") or cn.get("name", "")

    findings_en = en.get("key_physical_findings", [])
    findings_cn = cn.get("关键体征", [])
    symptom_en = " ".join(
        p for p in [_clean_template(en.get("chief_complaint")), _join(findings_en)] if p
    )
    symptom_zh = " ".join(
        p for p in [_clean_template(cn.get("主诉模板")), _join(findings_cn)] if p
    )

    plan_en, meds_en = _norm_meds_en(en.get("prescriptions", {}))
    plan_cn, meds_cn = _norm_meds_cn(cn.get("处方", {}))

    labs_en = en.get("labs") or en.get("labs_baseline") or []
    labs_cn = cn.get("检查") or cn.get("基线检查") or []

    return {
        "symptom_text": symptom_en,
        "symptom_text_zh": symptom_zh,
        "diagnosis": diagnosis,
        "diagnosis_zh": diagnosis_zh,
        "icd": en.get("icd10"),
        "category": en.get("category"),
        "treatment": {"plan": plan_en, "medications": meds_en},
        "treatment_zh": {"plan": plan_cn, "medications": meds_cn},
        "next_best_test": labs_en[0].replace("_", " ") if labs_en else "",
        "next_best_test_zh": labs_cn[0] if labs_cn else "",
        "supporting": [str(f).replace("_", " ") for f in findings_en],
        "supporting_zh": [str(f) for f in findings_cn],
    }


async def derm_count(session: AsyncSession) -> int:
    res = await session.execute(
        select(func.count())
        .select_from(DiagnosisEpisode)
        .where(DiagnosisEpisode.source == _SOURCE)
    )
    return int(res.scalar_one())


async def load_dermatology(session: AsyncSession) -> int:
    """Load the bilingual dermatology KB if not already present. Returns count.

    Concurrency-safe on Postgres via a transaction advisory lock (as with the
    general seed); SQLite dev is single-process.
    """
    if not (EN_FILE.exists() and CN_FILE.exists()):
        log.info("derm_files_absent", extra={"dir": str(DATA_DIR)})
        return 0

    if not settings.is_sqlite:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:k)").bindparams(k=_DERM_LOCK_KEY)
        )
    if await derm_count(session) > 0:
        return 0

    with open(EN_FILE, encoding="utf-8") as f:
        en_conditions = list(json.load(f)["conditions"].values())
    with open(CN_FILE, encoding="utf-8") as f:
        cn_conditions = list(json.load(f)["conditions"].values())

    episodes = [
        ep
        for en, cn in zip(en_conditions, cn_conditions, strict=False)
        if (ep := _build_episode(en, cn)) is not None
    ]
    if not episodes:
        return 0

    # Embed EN + ZH together so a query in either language retrieves the episode.
    vectors = await embed_texts(
        [f"{e['symptom_text']} {e['symptom_text_zh']}" for e in episodes]
    )

    for e, vec in zip(episodes, vectors, strict=True):
        session.add(
            DiagnosisEpisode(
                **e,
                outcome=_DEFAULT_OUTCOME,
                embedding=vec,
                source=_SOURCE,
                deidentified=True,
                snapshot_id=_SNAPSHOT,
            )
        )
    await session.commit()
    log.info("derm_loaded", extra={"episodes": len(episodes), "snapshot": _SNAPSHOT})
    return len(episodes)
