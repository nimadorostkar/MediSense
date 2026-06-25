import { Pill, ShieldCheck, ShieldAlert, ClipboardList, Activity } from "lucide-react";
import type { Treatment, Severity } from "../types";
import type { Strings } from "../lib/i18n";

/** Severity → colors for the drug-safety screen. */
function sevPalette(sev: Severity): { bg: string; fg: string; border: string } {
  switch (sev) {
    case "Contraindicated":
      return { bg: "#FEECEC", fg: "#B91C1C", border: "#F6CFCF" };
    case "Major":
      return { bg: "#FEF0E7", fg: "#C2410C", border: "#FAD5BE" };
    case "Moderate":
      return { bg: "#FEF3E2", fg: "#B45309", border: "#FCE3B6" };
    default:
      return { bg: "#F1F3F5", fg: "#64748B", border: "#E5E8EB" };
  }
}

function sevLabel(sev: Severity, t: Strings): string {
  return (
    { Contraindicated: t.sevContra, Major: t.sevMajor, Moderate: t.sevModerate, Minor: t.sevMinor }[
      sev
    ] || sev
  );
}

/**
 * The "best diagnosis → solution → prescription" block. Renders the recommended
 * plan, screened medications, and the drug-safety results beneath the differential.
 */
export default function TreatmentCard({ tx, t }: { tx: Treatment; t: Strings }) {
  const meds = tx.medications ?? [];
  const plan = tx.plan ?? [];
  const safety = tx.safety ?? [];

  return (
    <div className="mt-[14px] rounded-[12px] border border-[#E3F0EE] bg-[#F6FBFA] px-[16px] py-[14px]">
      <div className="mb-[10px] flex items-center gap-[7px]">
        <Pill size={15} strokeWidth={2} className="text-[#0F766E]" />
        <span className="text-[11px] font-semibold uppercase tracking-[0.4px] text-[#0F766E]">
          {t.txTitle}
        </span>
      </div>

      <div className="text-[14.5px] font-semibold text-ink-900">
        {t.txBest}: {tx.bestDiagnosis}
        {tx.icd ? <span className="ml-[7px] text-[12px] font-normal text-ink-300">{tx.icd}</span> : null}
      </div>
      {tx.rationale ? (
        <p className="mt-1 text-[13px] leading-[1.5] text-ink-500">{tx.rationale}</p>
      ) : null}

      {plan.length > 0 && (
        <div className="mt-[12px]">
          <div className="mb-1 flex items-center gap-[6px] text-[12px] font-semibold text-ink-700">
            <ClipboardList size={14} strokeWidth={1.9} /> {t.txPlan}
          </div>
          <ul className="ml-[6px] list-inside list-disc space-y-[2px] text-[13px] leading-[1.5] text-ink-600">
            {plan.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      {meds.length > 0 && (
        <div className="mt-[12px]">
          <div className="mb-[6px] flex items-center gap-[6px] text-[12px] font-semibold text-ink-700">
            <Pill size={14} strokeWidth={1.9} /> {t.txMeds}
          </div>
          <div className="flex flex-col gap-[6px]">
            {meds.map((m, i) => (
              <div
                key={i}
                className="rounded-[8px] border border-[#E5EBEA] bg-white px-[11px] py-[7px] text-[13px]"
              >
                <span className="font-semibold text-ink-900">{m.drug}</span>{" "}
                <span className="text-ink-600">
                  {[m.dose, m.route, m.frequency, m.duration].filter(Boolean).join(" · ")}
                </span>
                {m.note ? (
                  <div className="mt-[2px] text-[12px] font-medium text-[#B91C1C]">{m.note}</div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-[12px]">
        <div className="mb-[6px] flex items-center gap-[6px] text-[12px] font-semibold text-ink-700">
          {safety.length ? (
            <ShieldAlert size={14} strokeWidth={1.9} className="text-[#C2410C]" />
          ) : (
            <ShieldCheck size={14} strokeWidth={1.9} className="text-[#0F766E]" />
          )}
          {t.txSafety}
        </div>
        {safety.length === 0 ? (
          <p className="text-[13px] text-ink-500">{t.txClear}</p>
        ) : (
          <div className="flex flex-col gap-[5px]">
            {safety.map((f, i) => {
              const pal = sevPalette(f.severity);
              return (
                <div
                  key={i}
                  className="flex items-start gap-[8px] rounded-[8px] border px-[10px] py-[6px]"
                  style={{ background: pal.bg, borderColor: pal.border }}
                >
                  <span
                    className="mt-[1px] flex-none rounded-full px-[8px] py-[1px] text-[10.5px] font-bold uppercase tracking-[0.3px]"
                    style={{ background: "#fff", color: pal.fg }}
                  >
                    {sevLabel(f.severity, t)}
                  </span>
                  <span className="text-[12.5px] leading-[1.45]" style={{ color: pal.fg }}>
                    {f.message}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {tx.monitoring ? (
        <div className="mt-[12px] flex items-start gap-[8px] border-t border-[#E3F0EE] pt-[11px]">
          <Activity size={14} strokeWidth={1.9} className="mt-px flex-none text-[#0F766E]" />
          <span className="text-[12.5px] leading-[1.45] text-ink-600">
            <b className="text-ink-900">{t.txMonitor}:</b> {tx.monitoring}
          </span>
        </div>
      ) : null}

      <p className="mt-[10px] text-[11.5px] text-ink-300">{t.txConfirm}</p>
    </div>
  );
}
