import type { LucideIcon } from "lucide-react";
import { Sparkles } from "lucide-react";
import type { Strings } from "../lib/i18n";
import type { QuickLook } from "../lib/api";
import Logo from "./Logo";
import Composer from "./Composer";

export interface Chip {
  label: string;
  sample: string;
  icon: LucideIcon;
}

export default function HeroInput({
  t,
  draft,
  onChange,
  onSend,
  recording,
  micSupported,
  onMic,
  chips,
  preview,
  previewLoading,
}: {
  t: Strings;
  draft: string;
  onChange: (v: string) => void;
  onSend: () => void;
  recording: boolean;
  micSupported: boolean;
  onMic: () => void;
  chips: Chip[];
  preview: QuickLook;
  previewLoading: boolean;
}) {
  // Once the user starts typing, collapse the hero: hide the logo, title,
  // subtitle and chips, and show a LIVE, file-grounded reading of what has been
  // typed — recognized clinical keywords + candidate conditions (from the
  // uploaded files, no AI) — updating in real time in place of a static label.
  // The <Composer> stays at a fixed position in the tree so React keeps the
  // textarea mounted and focus is never lost on the first keystroke.
  const typing = draft.trim().length > 0;

  return (
    <div
      className={`flex flex-1 flex-col items-center py-10 ${
        typing ? "" : "justify-center gap-1"
      }`}
    >
      {typing ? (
        <div className="flex flex-1 items-center justify-center">
          <LivePreview t={t} preview={preview} loading={previewLoading} />
        </div>
      ) : (
        <>
          <Logo size={170} hero />
          <h1 className="mb-1 mt-[18px] text-[23px] font-bold tracking-[-0.4px] text-ink-900">
            {t.heroTitle}
          </h1>
          <p className="mb-[22px] text-[14px] text-ink-400">{t.heroSub}</p>
        </>
      )}

      <Composer
        key="composer"
        t={t}
        value={draft}
        onChange={onChange}
        onSend={onSend}
        placeholder={t.inputPh}
        recording={recording}
        micSupported={micSupported}
        onMic={onMic}
      />

      {!typing && (
        <div className="mt-4 grid w-full max-w-[640px] grid-cols-2 gap-[10px] sm:grid-cols-4">
          {chips.map((c) => {
            const Icon = c.icon;
            return (
              <button
                key={c.label}
                type="button"
                onClick={() => onChange(c.sample)}
                className="flex flex-col items-center gap-[7px] rounded-xl border border-[#ECEDEF] bg-[#F6F7F9] px-[6px] py-[11px] text-ink-900 shadow-[0_1px_2px_rgba(15,23,42,0.03)] transition-all duration-150 hover:-translate-y-[2px] hover:border-[#c9d6f7] hover:bg-white hover:shadow-chip"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-[9px] bg-accent-soft text-accent">
                  <Icon size={17} strokeWidth={1.8} />
                </span>
                <span className="text-[12px] font-medium">{c.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

/**
 * Real-time reading of the case as it is typed. Shows candidate conditions and
 * recognized clinical keywords, all matched deterministically from the uploaded
 * files. Empty until something clinical is recognized (never a guess).
 */
function LivePreview({
  t,
  preview,
  loading,
}: {
  t: Strings;
  preview: QuickLook;
  loading: boolean;
}) {
  const { keywords, diagnoses } = preview;
  const hasContent = keywords.length > 0 || diagnoses.length > 0;

  return (
    <div className="w-full max-w-[560px] px-2 text-center">
      <div className="mb-4 flex items-center justify-center gap-2 text-accent">
        <Sparkles size={18} strokeWidth={1.9} className={loading ? "animate-pulse" : ""} />
        <span className="text-[13px] font-semibold uppercase tracking-[0.5px]">
          {t.liveReading}
        </span>
      </div>

      {diagnoses.length > 0 && (
        <div className="mb-4">
          <div className="mb-[9px] text-[11px] font-semibold uppercase tracking-[0.4px] text-ink-300">
            {t.livePossible}
          </div>
          <div className="flex flex-col gap-2">
            {diagnoses.map((d) => {
              const pct = Math.max(0, Math.min(100, Math.round(d.probability)));
              return (
                <div
                  key={d.condition + d.icd}
                  className="flex items-center gap-3 rounded-[12px] border border-[#E7E9EE] bg-white/80 px-[14px] py-[10px] shadow-[0_1px_2px_rgba(15,23,42,0.04)]"
                >
                  <span className="flex-1 truncate text-left text-[15px] font-semibold text-ink-900">
                    {d.condition}
                    {d.icd ? (
                      <span className="ml-[7px] text-[12px] font-normal text-ink-300">{d.icd}</span>
                    ) : null}
                  </span>
                  <span className="h-[6px] w-[70px] flex-none overflow-hidden rounded-full bg-[#EEF0F2]">
                    <span
                      className="block h-full rounded-full bg-gradient-to-r from-[#60A5FA] to-[#2563EB] transition-[width] duration-300"
                      style={{ width: `${pct}%` }}
                    />
                  </span>
                  <span className="w-[38px] flex-none text-right text-[13px] font-bold tabular-nums text-ink-900">
                    {pct}%
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {keywords.length > 0 && (
        <div className="mb-3">
          <div className="mb-[9px] text-[11px] font-semibold uppercase tracking-[0.4px] text-ink-300">
            {t.liveRecognized}
          </div>
          <div className="flex flex-wrap justify-center gap-[7px]">
            {keywords.map((k) => (
              <span
                key={k}
                className="rounded-full border border-[#DCE6FA] bg-accent-soft px-[11px] py-[4px] text-[12.5px] font-medium text-accent"
              >
                {k}
              </span>
            ))}
          </div>
        </div>
      )}

      {!hasContent && (
        <p className="text-[14px] text-ink-300">{t.liveListening}</p>
      )}

      {hasContent && <p className="mt-3 text-[11.5px] text-ink-300">{t.liveHint}</p>}
    </div>
  );
}
