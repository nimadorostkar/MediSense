import type { LucideIcon } from "lucide-react";
import type { Strings } from "../lib/i18n";
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
}: {
  t: Strings;
  draft: string;
  onChange: (v: string) => void;
  onSend: () => void;
  recording: boolean;
  micSupported: boolean;
  onMic: () => void;
  chips: Chip[];
}) {
  // Once the user starts typing, collapse the hero: hide the logo, title,
  // subtitle and chips, show "Fast Answer…" centered, and drop the input down.
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
          <h1 className="text-[26px] font-bold tracking-[-0.4px] text-ink-900">{t.fastAnswer}</h1>
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
