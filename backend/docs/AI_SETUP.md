# MediSense — AI Setup (Zhipu GLM)

How to turn on the AI layer. **MediSense runs fully without it** — offline it uses
a deterministic hashing embedder and the rules/retrieval pipeline. Adding a Zhipu
key upgrades two things:

1. **Embeddings** — real `embedding-3` vectors for semantic retrieval (much better
   than the offline hashing fallback).
2. **Reasoning** — a grounded, citation-required **Zhipu GLM** layer that refines
   the case summary (rules/safety still run last and can veto it).

---

## 1. Get a key

Sign up at Zhipu AI (BigModel) → **https://open.bigmodel.cn/** → create an API key.
It looks like `xxxxxxxx.xxxxxxxx`. (International endpoint also exists; it's
swappable via `ZHIPU_BASE_URL`.)

---

## 2. Configure `.env`

```bash
# Required to enable real embeddings:
ZHIPU_API_KEY=your-key-here
ZHIPU_BASE_URL=https://open.bigmodel.cn/api/paas/v4   # China; swap for intl if needed

# Models (config-driven — verify current ids against Zhipu docs):
LLM_CHAT_MODEL=glm-4.6
EMBEDDING_MODEL=embedding-3

# Turn ON the grounded GLM reasoning layer (off by default):
LLM_REASONING=true

# Bounded cost / resilience:
LLM_MAX_TOKENS=1024
LLM_TIMEOUT_SECONDS=12
```

> **What each flag does**
> - **Just `ZHIPU_API_KEY`** (reasoning off) → real `embedding-3` retrieval; no LLM text generation.
> - **`ZHIPU_API_KEY` + `LLM_REASONING=true`** → embeddings **and** the grounded GLM summary.
> - **No key** → fully offline (hashing embedder, deterministic pipeline). `LLM_REASONING=true` with no key stays offline.

The health endpoint reflects it: `"llmReasoning": true` only when a key is present
**and** reasoning is on.

---

## 3. Verify

```bash
# Docker:
ZHIPU_API_KEY=your-key docker compose up -d --build
# or local: set the vars in .env, then
uvicorn app.main:app --port 8787

curl localhost:8787/api/health
# → "llmReasoning": true   when key + LLM_REASONING are set
```

A clinical call will now use semantic embeddings (sharper differentials) and, with
reasoning on, a grounded `summary`:

```bash
curl -X POST localhost:8787/api/clinical -H 'content-type: application/json' \
  -d '{"messages":[{"role":"doctor","text":"62F fever, productive cough, pleuritic chest pain, RR 22 SpO2 94"}],"lang":"en"}'
```

---

## 4. How it's wired (where to look)

| Concern | File |
|---|---|
| Config / flags | `app/config.py` (`zhipu_*`, `llm_chat_model`, `embedding_model`, `llm_reasoning`) |
| Provider interface (swap any LLM) | `app/ai/provider.py` |
| Zhipu implementation (OpenAI-compatible SDK) | `app/ai/zhipu.py` |
| Embeddings + offline fallback | `app/engine/embeddings.py` |
| Grounded reasoner (system prompt, citation rule) | `app/engine/reasoner.py` |

The provider is isolated behind `LLMProvider` / `EmbeddingProvider`, so switching
to a different model or vendor is **configuration, not code**.

---

## 5. Safety, resilience & cost (built in)

- **Grounded + cited:** the reasoner's system prompt forces every claim to cite a
  retrieved episode and forbids inventing drugs/doses. Uncited output is suppressed.
- **Rules still win:** the safety/rules layer runs **last** and re-vetoes anything
  the LLM produces — generated text cannot override a red flag or a hard drug block.
- **Never blocks:** timeouts + retries with backoff; on any Zhipu failure the system
  falls back to the deterministic pipeline and labels it *"degraded mode — reasoner
  offline"*. The response is never held indefinitely on the LLM.
- **Bounded cost:** `LLM_MAX_TOKENS` caps each call; calls are logged.
- **Re-embedding:** changing `EMBEDDING_MODEL` changes the vector space — reseed /
  re-embed the KB (`docker compose down -v` on Postgres, or delete the SQLite file)
  so stored episode vectors match the query embeddings.

> **Model identifiers:** defaults (`glm-4.6`, `embedding-3`) reflect this build.
> Verify against Zhipu's current docs and update the env if they changed — no code
> change needed.
