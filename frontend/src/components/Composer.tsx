import { useEffect, useRef } from "react";
import { Paperclip, Mic, SendHorizontal } from "lucide-react";
import type { Strings } from "../lib/i18n";

export default function Composer({
  t,
  value,
  onChange,
  onSend,
  placeholder,
  recording,
  micSupported,
  onMic,
  card = true,
}: {
  t: Strings;
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  placeholder: string;
  recording: boolean;
  micSupported: boolean;
  onMic: () => void;
  /** Hero card (centered, max-width) vs. inline conversation composer. */
  card?: boolean;
}) {
  const ref = useRef<HTMLTextAreaElement>(null);

  // Auto-grow the textarea up to a cap.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 150) + "px";
  }, [value]);

  const active = value.trim().length > 0;

  return (
    <div
      className={`group rounded-2xl border border-line bg-white px-[18px] pb-[10px] pt-[14px] shadow-input transition-[border-color,box-shadow] focus-within:border-[#bfd0f7] focus-within:shadow-focus ${
        card ? "w-full max-w-[640px]" : "mb-[18px] flex-none"
      }`}
    >
      <label htmlFor="ms-composer" className="sr-only">
        {placeholder}
      </label>
      <textarea
        id="ms-composer"
        ref={ref}
        rows={1}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSend();
          }
        }}
        className="max-h-[150px] w-full resize-none border-none bg-transparent text-[15px] leading-[1.5] text-ink-900 outline-none"
      />
      <div className="mt-2 flex items-center">
        <div className="flex items-center gap-[14px] text-ink-400">
          <button
            type="button"
            title={t.attach}
            aria-label={t.attach}
            className="flex h-9 w-9 items-center justify-center rounded-lg transition-colors hover:text-ink-700"
          >
            <Paperclip size={18} strokeWidth={1.6} />
          </button>
          {micSupported && (
            <button
              type="button"
              onClick={onMic}
              title={recording ? t.micStop : t.micRec}
              aria-label={recording ? t.micStop : t.micRec}
              aria-pressed={recording}
              className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
                recording ? "animate-blink text-[#DC2626]" : "text-ink-400 hover:text-ink-700"
              }`}
            >
              <Mic size={18} strokeWidth={1.6} />
            </button>
          )}
        </div>
        <button
          type="button"
          onClick={onSend}
          disabled={!active}
          title={t.send}
          aria-label={t.send}
          className={`ml-auto flex h-[34px] w-[34px] items-center justify-center rounded-[10px] transition-all ${
            active
              ? "cursor-pointer bg-accent text-white hover:brightness-110"
              : "cursor-default bg-transparent text-ink-300"
          }`}
        >
          <SendHorizontal size={17} strokeWidth={1.7} />
        </button>
      </div>
    </div>
  );
}
