import { AlertTriangle, FlaskConical } from "lucide-react";
import type { Message } from "../types";
import type { Strings } from "../lib/i18n";
import { bandLabel } from "../lib/i18n";
import { normBand } from "../lib/api";
import { bandPalette } from "../lib/bands";

/**
 * AI message card: optional red-flag banner, summary, ranked differential rows
 * (condition + ICD, probability %, colored bar, confidence badge), next-best
 * test line, and an advisory note.
 */
export default function DifferentialCard({ msg, t }: { msg: Message; t: Strings }) {
  const dx = msg.dx;
  const items = dx?.differential ?? [];

  return (
    <div className="max-w-[92%] rounded-[4px_16px_16px_16px] border border-line bg-white px-[18px] py-[15px] shadow-card">
      <div className="mb-[10px] flex items-center gap-[7px]">
        <span className="h-4 w-4 rounded-[5px] bg-gradient-to-br from-[#60A5FA] to-[#2563EB]" />
        <span className="text-[11px] font-semibold uppercase tracking-[0.4px] text-accent">
          {t.suggestion}
        </span>
      </div>

      {dx?.redFlag ? (
        <div className="mb-3 flex items-start gap-2 rounded-[10px] border border-[#F6CFCF] bg-[#FEECEC] px-3 py-[10px]">
          <AlertTriangle size={17} strokeWidth={1.8} className="mt-px flex-none text-[#DC2626]" />
          <span className="text-[13px] font-medium leading-[1.45] text-[#B91C1C]">
            {dx.redFlag}
          </span>
        </div>
      ) : null}

      {dx?.summary ? (
        <p className="whitespace-pre-wrap text-[14.5px] leading-[1.6] text-[#1E293B]">
          {dx.summary}
        </p>
      ) : null}

      {!dx && msg.text ? (
        <p className="whitespace-pre-wrap text-[14.5px] leading-[1.6] text-[#1E293B]">{msg.text}</p>
      ) : null}

      {items.length > 0 && (
        <div className="mt-[13px] flex flex-col gap-[15px]">
          {items.map((it, i) => {
            const band = normBand(it.confidence);
            const pct = Math.max(0, Math.min(100, Math.round(Number(it.probability) || 0)));
            const pal = bandPalette(band);
            return (
              <div key={i}>
                <div className="flex items-baseline justify-between gap-3">
                  <div className="text-[14.5px] font-semibold leading-[1.35] text-ink-900">
                    {it.condition}
                    {it.icd ? (
                      <span className="ml-[7px] text-[12px] font-normal text-ink-300">
                        {it.icd}
                      </span>
                    ) : null}
                  </div>
                  <span className="flex-none text-[14px] font-bold tabular-nums text-ink-900">
                    {pct}%
                  </span>
                </div>
                <div className="mt-[10px] h-[6px] overflow-hidden rounded-full bg-[#EEF0F2]">
                  <div
                    className="h-full rounded-full transition-[width] duration-500"
                    style={{ width: `${pct}%`, background: pal.bar }}
                  />
                </div>
                <div className="mt-2 flex items-center gap-[9px]">
                  <span
                    className="flex-none rounded-full px-[9px] py-[2px] text-[11px] font-semibold"
                    style={{ background: pal.bg, color: pal.fg }}
                  >
                    {bandLabel(band, t)}
                  </span>
                  <span className="text-[12.5px] leading-[1.4] text-ink-500">{it.because}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {dx?.nextBestTest ? (
        <div className="mt-[14px] flex items-start gap-[9px] border-t border-[#F0F1F3] pt-[13px]">
          <FlaskConical size={16} strokeWidth={1.8} className="mt-px flex-none text-accent" />
          <span className="text-[13px] leading-[1.45] text-[#475569]">
            <b className="text-ink-900">{t.nextBest}</b> {dx.nextBestTest}
          </span>
        </div>
      ) : null}

      {items.length > 0 && <p className="mt-3 text-[11.5px] text-ink-300">{t.advisory}</p>}
    </div>
  );
}
