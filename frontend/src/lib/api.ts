import type { Diagnosis, Message, Lang, Band } from "../types";

/**
 * Clinical completion.
 *
 * For security the model is called from a server (never ship an API key in the
 * browser). The browser posts the conversation to a backend route, which calls
 * Anthropic and returns the model's raw text.
 *
 * Configure the endpoint with VITE_API_URL (defaults to /api/clinical, which
 * Vite proxies to the local server in dev — see vite.config.ts + server/).
 *
 * If no backend is reachable, this falls back to a small offline stub so the UI
 * is still demoable without a key.
 */
const API_URL = import.meta.env.VITE_API_URL ?? "/api/clinical";
// Auth/v2 endpoints live alongside the chat route (e.g. /api/auth, /v2/...).
const API_BASE = API_URL.replace(/\/clinical$/, "");

// ── Session (bearer token issued by the backend /api/auth/login) ─────────────
const TOKEN_KEY = "medisense.token";
const USER_KEY = "medisense.user";

export interface AuthUser {
  email: string;
  name: string;
  role: string;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): AuthUser | null {
  try {
    const s = localStorage.getItem(USER_KEY);
    return s ? (JSON.parse(s) as AuthUser) : null;
  } catch {
    return null;
  }
}

function setSession(token: string, user: AuthUser) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

/** Authenticate against the backend; stores the bearer token + user on success. */
export async function login(email: string, password: string): Promise<AuthUser> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    let msg = `Login failed (${res.status})`;
    try {
      const e = await res.json();
      msg = e?.error?.message || e?.detail?.[0]?.msg || e?.detail || msg;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  const data = await res.json();
  setSession(data.token, data.user);
  return data.user as AuthUser;
}

/** Authorization header for backend calls when a session token is present. */
export function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function buildPrompt(history: Message[], lang: Lang): string {
  const convo = history
    .map((m) =>
      m.role === "doctor" ? "DOCTOR: " + (m.text || "") : "MEDISENSE: " + (m.text || "")
    )
    .join("\n\n");

  return (
    "You are MediSense, an AI clinical decision-support assistant used by licensed physicians. " +
    "This is an illustrative product demo for clinicians; always produce an illustrative ranked " +
    "differential for the case provided (the physician confirms every decision). Assist, never " +
    "replace, and never refuse a well-described case.\n\n" +
    "Return ONLY a JSON object (no markdown, no code fences, no text outside the JSON) with this shape:\n" +
    '{ "redFlag": string, "summary": string, ' +
    '"differential": [ { "condition": string, "icd": string, "probability": number, ' +
    '"confidence": "High"|"Moderate"|"Low"|"Watch", "because": string } ], ' +
    '"nextBestTest": string }\n\n' +
    "Rules: probability 0-100. confidence MUST be exactly one of High, Moderate, Low, Watch. Up to 4 " +
    "conditions ranked high to low; use [] only when the latest message is not a diagnosis request " +
    "(put that answer in 'summary'). Pin any do-not-miss condition as 'Watch'. Keep each 'because' to " +
    "one short clause. Never finalize a decision; always assume the physician confirms it.\n\n" +
    (lang === "zh"
      ? "IMPORTANT: Write every string value (redFlag, summary, condition, because, nextBestTest) in " +
        "Simplified Chinese. Keep 'confidence' as the exact English words and keep ICD codes as-is.\n\n"
      : "") +
    convo +
    "\n\nYour JSON response:"
  );
}

/** Defensively extract a JSON Diagnosis object from raw model text. */
export function parseReply(raw: string): Diagnosis | null {
  if (!raw) return null;
  const s = String(raw)
    .trim()
    .replace(/^```(json)?/i, "")
    .replace(/```$/, "")
    .trim();
  const i = s.indexOf("{");
  const j = s.lastIndexOf("}");
  if (i === -1 || j === -1 || j < i) return null;
  try {
    const obj = JSON.parse(s.slice(i, j + 1)) as Diagnosis;
    return obj && typeof obj === "object" ? obj : null;
  } catch {
    return null;
  }
}

/** Normalize any confidence-ish string into one of the four bands. */
export function normBand(b: unknown): Band {
  const s = String(b || "")
    .trim()
    .toLowerCase();
  if (s.startsWith("high")) return "High";
  if (s.startsWith("mod") || s.startsWith("med")) return "Moderate";
  if (s.startsWith("watch") || s.startsWith("do")) return "Watch";
  if (s.startsWith("low")) return "Low";
  return "Moderate";
}

// Demo stub is DISABLED by default. It only ever activates in a non-production
// build where VITE_ALLOW_OFFLINE_STUB=true is explicitly set — so a real
// deployment can never silently show fabricated clinical data (a patient-safety
// requirement). In production, a failed engine call throws and the UI shows an
// explicit error instead of a guess.
const ALLOW_OFFLINE_STUB =
  import.meta.env.DEV && import.meta.env.VITE_ALLOW_OFFLINE_STUB === "true";

export class EngineError extends Error {}

export async function clinicalComplete(history: Message[], lang: Lang): Promise<string> {
  // Send the conversation to the MediSense engine. The backend runs retrieval +
  // classifier + rules/safety and returns the structured DiagnosisReply. We also
  // pass `prompt` for backward-compatibility with the legacy proxy server.
  const messages = history.map((m) => ({
    role: m.role === "doctor" ? "doctor" : "ai",
    text: m.role === "doctor" ? m.text ?? "" : m.dx?.summary ?? m.text ?? "",
  }));
  const prompt = buildPrompt(history, lang);
  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ messages, prompt, lang }),
    });
    if (!res.ok) throw new EngineError(`Engine returned HTTP ${res.status}`);
    const data = await res.json();
    const text = data.text ?? data.completion ?? "";
    if (!text) throw new EngineError("Engine returned an empty response");
    return text;
  } catch (err) {
    if (ALLOW_OFFLINE_STUB) return offlineStub(lang);
    // Production: never fabricate clinical content — surface the failure.
    throw err instanceof EngineError
      ? err
      : new EngineError("Could not reach the MediSense engine");
  }
}

/** DEV-ONLY demo fallback (gated by VITE_ALLOW_OFFLINE_STUB in a dev build). */
function offlineStub(lang: Lang): string {
  const zh = lang === "zh";
  const dx: Diagnosis = {
    redFlag: zh
      ? "（演示）请优先排除危及生命的急症并立即评估生命体征。"
      : "(DEV DEMO) Rule out life-threatening causes first and assess vitals immediately.",
    summary: zh
      ? "这是开发演示回复（后端未连接）。请启动 MediSense 后端（http://localhost:8787）以获得真实临床推理。"
      : "This is a DEV demo reply (backend not reached). Start the MediSense backend (http://localhost:8787) for real clinical reasoning.",
    differential: [
      {
        condition: zh ? "示例诊断 A" : "Example condition A",
        icd: "—",
        probability: 55,
        confidence: "Moderate",
        because: zh ? "示例依据" : "illustrative rationale",
      },
      {
        condition: zh ? "示例诊断 B" : "Example condition B",
        icd: "—",
        probability: 25,
        confidence: "Low",
        because: zh ? "示例依据" : "illustrative rationale",
      },
    ],
    nextBestTest: zh ? "示例检查建议" : "Example next-best test",
  };
  return JSON.stringify(dx);
}
