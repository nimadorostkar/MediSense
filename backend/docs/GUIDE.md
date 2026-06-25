# MediSense Backend — Short Guide

Three things: **how it works**, **how to add database data**, **how to run**.

---

## 1. How it works

A doctor's free-text case goes through a fixed, safety-ordered pipeline:

```
enrich → retrieve → classify → calibrate → rules/safety (LAST, hard veto)
       → rank & explain → [optional] Zhipu GLM reasoning
treatment:  recommend (outcome-weighted) → drug-safety screen (hard veto)
```

- **enrich** — parse age/sex/vitals/allergies/meds from the text.
- **retrieve** — embed the case, find the most similar past **episodes** (pgvector ANN, or in-process cosine on SQLite).
- **classify + calibrate** — outcome-weighted vote → honest probabilities.
- **rules/safety (last)** — surfaces do-not-miss red flags (ACS, sepsis, stroke…) and can override any statistical output. Allergy/contraindication = hard block.
- **drug-safety screen** — allergy + cross-reactivity + interactions + dosing bounds before any drug is shown.

Every response is **version-stamped**, **audited** (immutable hash-chain), and carries `requiresPhysicianConfirmation: true` — the system never auto-commits a decision.

The whole thing answers from `data/episodes.json` (the knowledge base) — **the more good episodes you add, the smarter it gets.**

---

## 2. How to add database data

The knowledge base is **outcome-labelled episodes**: `symptoms → diagnosis → treatment → recovery outcome (0–1)`. Three ways to add them:

### A) Edit the seed file (loaded on first start)
Add entries to `data/episodes.json` → `episodes[]`:
```json
{
  "symptomText": "30F sudden severe headache, neck stiffness, photophobia, fever",
  "diagnosis": "Meningitis", "icd": "G03.9", "outcome": 0.85,
  "nextBestTest": "Lumbar puncture",
  "supporting": ["headache", "neck stiffness", "photophobia", "fever"],
  "treatment": {"plan": ["Urgent LP", "Empirical antibiotics"], "medications": [
    {"drug": "Ceftriaxone", "dose": "2 g", "route": "IV", "frequency": "twice daily", "duration": "7 days"}
  ]}
}
```
Then reload (seeding only runs when the KB is empty):
```bash
rm -f medisense.db                 # SQLite: wipe to force a reseed
uvicorn app.main:app --port 8787   # reseeds on startup
```
> Also add the condition (with ICD + Chinese label) to `data/code_maps.json`, and any new drugs to `data/drug_reference.json`, so labels and safety screening cover it.

### B) Add live via the API (embeds + indexes immediately, no restart)
```bash
TOKEN=$(python -c "from app.security.oidc import mint_dev_token; print(mint_dev_token('p1','Dr Lin','physician'))")
curl -X POST localhost:8787/v2/episodes \
  -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"symptomText":"...","diagnosis":"Influenza","icd":"J11.1","outcome":0.93,"nextBestTest":"PCR","treatment":{"plan":[],"medications":[]}}'
```
Each episode passes the **data-quality pipeline** (validation + de-identification); bad data is quarantined (`422`), never silently admitted.

### C) Bulk-load your real corpus (out-of-band)
The seed format scales to the 3,000+ Chinese corpus. Point `data/episodes.json` at your de-identified export (same shape) and reseed, or loop `POST /v2/episodes` from a script. Replace `data/drug_reference.json` with a licensed China formulary.

> SQLite reseeds when empty; on **Postgres** the data persists in the `pgdata` volume — wipe with `docker compose down -v` to reseed from the file.

---

## 3. How to run

### Zero-setup (SQLite, no external services)
```bash
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8787        # auto-creates + seeds SQLite
```
Docs at **http://localhost:8787/docs**.

### Full stack (Docker: API + Postgres/pgvector + Redis)
```bash
docker compose up -d --build
curl localhost:8787/api/health
```

### Smoke test
```bash
curl -X POST localhost:8787/api/clinical -H 'content-type: application/json' \
  -d '{"messages":[{"role":"doctor","text":"67M chest pain radiating to left arm, diaphoretic, HR 118 BP 92/60"}],"lang":"en"}'
# → red-flag-first differential (ACS), version stamps, requiresPhysicianConfirmation: true
```

### Common commands
```bash
make test     # full test suite (incl. safety golden gate)
make check    # ruff + mypy + tests
make smoke    # health + ACS smoke
make dev      # uvicorn with --reload
```

### Enable real AI (optional)
Set in `.env`: `ZHIPU_API_KEY=...` and `LLM_REASONING=true` for real Zhipu
embeddings + grounded GLM reasoning. Without a key it runs fully offline on a
deterministic hashing embedder. **Full steps: see `AI_SETUP.md`.**
