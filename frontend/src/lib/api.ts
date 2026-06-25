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

export async function clinicalComplete(history: Message[], lang: Lang): Promise<string> {
  const prompt = buildPrompt(history, lang);
  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt, lang }),
    });
    if (!res.ok) throw new Error("bad status " + res.status);
    const data = await res.json();
    const text = data.text ?? data.completion ?? "";
    if (!text) throw new Error("empty");
    return text;
  } catch {
    return offlineStub(lang);
  }
}

/** Demo fallback so the UI works without a backend / API key. */
function offlineStub(lang: Lang): string {
  const zh = lang === "zh";
  const dx: Diagnosis = {
    redFlag: zh
      ? "（演示）请优先排除危及生命的急症并立即评估生命体征。"
      : "(Demo) Rule out life-threatening causes first and assess vitals immediately.",
    summary: zh
      ? "这是离线演示回复。连接后端并设置 ANTHROPIC_API_KEY 后即可获得真实的临床推理。"
      : "This is an offline demo reply. Connect the server with an ANTHROPIC_API_KEY to get real clinical reasoning.",
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
