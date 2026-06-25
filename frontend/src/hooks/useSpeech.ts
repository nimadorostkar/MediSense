import { useEffect, useRef, useState } from "react";
import type { Lang } from "../types";

/**
 * Web Speech API dictation. Returns recording state, a toggle, and whether the
 * browser supports SpeechRecognition at all. Language follows the UI language.
 */
export function useSpeech(lang: Lang, onTranscript: (text: string) => void) {
  const [recording, setRecording] = useState(false);
  const recRef = useRef<any>(null);
  const baseRef = useRef("");

  // Keep the latest callback without re-creating recognition.
  const cbRef = useRef(onTranscript);
  cbRef.current = onTranscript;

  const supported =
    typeof window !== "undefined" &&
    !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

  useEffect(
    () => () => {
      try {
        recRef.current?.stop();
      } catch {
        /* noop */
      }
    },
    []
  );

  function start(currentDraft: string) {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) return;
    const rec = new SR();
    rec.lang = lang === "zh" ? "zh-CN" : "en-US";
    rec.interimResults = true;
    rec.continuous = true;
    baseRef.current = currentDraft ? currentDraft.replace(/\s+$/, "") + " " : "";
    rec.onresult = (e: any) => {
      let t = "";
      for (let k = 0; k < e.results.length; k++) t += e.results[k][0].transcript;
      cbRef.current((baseRef.current + t).replace(/^\s+/, ""));
    };
    rec.onend = () => {
      setRecording(false);
      recRef.current = null;
    };
    rec.onerror = () => {
      setRecording(false);
      recRef.current = null;
    };
    recRef.current = rec;
    try {
      rec.start();
      setRecording(true);
    } catch {
      /* start() throws if already started */
    }
  }

  function toggle(currentDraft: string) {
    if (recording) {
      try {
        recRef.current?.stop();
      } catch {
        /* noop */
      }
      setRecording(false);
    } else {
      start(currentDraft);
    }
  }

  return { recording, supported, toggle };
}
