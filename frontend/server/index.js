// ─────────────────────────────────────────────────────────────────────────────
// MediSense API server
// ─────────────────────────────────────────────────────────────────────────────
// A tiny Express route that proxies the conversation to Anthropic. The API key
// stays on the server and is NEVER exposed to the browser. The frontend posts
// { prompt, lang } to POST /api/clinical and receives { text }.
//
//   1. cp .env.example .env   and set ANTHROPIC_API_KEY
//   2. npm run server          (listens on PORT, default 8787)
//   3. npm run dev             (Vite proxies /api -> this server)
//
// In production, serve the built `dist/` from this same server (see bottom) or
// behind your own gateway. Either way the key lives only here.

import express from "express";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Minimal .env loader (no dependency) so `node server/index.js` just works.
loadEnv(join(__dirname, "..", ".env"));

const PORT = process.env.PORT || 8787;
const API_KEY = process.env.ANTHROPIC_API_KEY || "";
const MODEL = process.env.ANTHROPIC_MODEL || "claude-sonnet-4-20250514";
const ANTHROPIC_URL = "https://api.anthropic.com/v1/messages";

const app = express();
app.use(express.json({ limit: "1mb" }));

app.get("/api/health", (_req, res) => {
  res.json({ ok: true, model: MODEL, keyConfigured: Boolean(API_KEY) });
});

app.post("/api/clinical", async (req, res) => {
  const prompt = String(req.body?.prompt || "");
  if (!prompt) return res.status(400).json({ error: "Missing prompt." });

  if (!API_KEY) {
    // Let the frontend fall back to its offline demo stub.
    return res.status(503).json({ error: "ANTHROPIC_API_KEY not configured on the server." });
  }

  try {
    const upstream = await fetch(ANTHROPIC_URL, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 1024,
        messages: [{ role: "user", content: prompt }],
      }),
    });

    if (!upstream.ok) {
      const detail = await upstream.text();
      console.error("Anthropic error", upstream.status, detail);
      return res.status(502).json({ error: "Upstream model error." });
    }

    const data = await upstream.json();
    const text = Array.isArray(data.content)
      ? data.content
          .filter((b) => b.type === "text")
          .map((b) => b.text)
          .join("")
      : "";
    res.json({ text });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Server error calling the model." });
  }
});

// Optionally serve the built frontend from the same origin in production.
const distDir = join(__dirname, "..", "dist");
if (existsSync(distDir)) {
  app.use(express.static(distDir));
  app.get("*", (_req, res) => res.sendFile(join(distDir, "index.html")));
}

app.listen(PORT, () => {
  console.log(`MediSense API listening on http://localhost:${PORT}`);
  if (!API_KEY) {
    console.warn("⚠  ANTHROPIC_API_KEY is not set — the UI will use its offline demo reply.");
  }
});

// ── helpers ──────────────────────────────────────────────────────────────────
function loadEnv(path) {
  if (!existsSync(path)) return;
  try {
    for (const line of readFileSync(path, "utf8").split("\n")) {
      const m = line.match(/^\s*([\w.-]+)\s*=\s*(.*)\s*$/);
      if (!m) continue;
      const key = m[1];
      let val = m[2].replace(/^["']|["']$/g, "");
      if (process.env[key] === undefined) process.env[key] = val;
    }
  } catch {
    /* ignore */
  }
}
