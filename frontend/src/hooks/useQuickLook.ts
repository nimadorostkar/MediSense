import { useEffect, useRef, useState } from "react";
import { quickLook, type QuickLook } from "../lib/api";
import type { Lang } from "../types";

const EMPTY: QuickLook = { keywords: [], diagnoses: [] };

/**
 * Debounced, file-grounded live preview of the case being typed.
 *
 * Watches `draft` and, after a short pause, asks the backend for recognised
 * keywords + candidate conditions (deterministic, no AI). Each new keystroke
 * aborts the in-flight request so only the latest text is reflected. Returns
 * the current preview and whether a lookup is in flight.
 */
export function useQuickLook(draft: string, lang: Lang, enabled: boolean) {
  const [preview, setPreview] = useState<QuickLook>(EMPTY);
  const [loading, setLoading] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const text = draft.trim();
    if (!enabled || !text) {
      abortRef.current?.abort();
      setPreview(EMPTY);
      setLoading(false);
      return;
    }

    setLoading(true);
    const timer = setTimeout(async () => {
      abortRef.current?.abort();
      const ctrl = new AbortController();
      abortRef.current = ctrl;
      const result = await quickLook(text, lang, ctrl.signal);
      if (!ctrl.signal.aborted) {
        setPreview(result);
        setLoading(false);
      }
    }, 220);

    return () => clearTimeout(timer);
  }, [draft, lang, enabled]);

  useEffect(() => () => abortRef.current?.abort(), []);

  return { preview, loading };
}
