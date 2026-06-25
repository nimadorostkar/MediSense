import { Globe } from "lucide-react";
import type { Strings } from "../lib/i18n";
import Logo from "./Logo";

const NAV_KEYS = ["platform", "solutions", "evidence", "integrations", "pricing"] as const;

export default function Header({
  t,
  onToggleLang,
  onSignIn,
  onHome,
}: {
  t: Strings;
  onToggleLang: () => void;
  onSignIn: () => void;
  onHome: () => void;
}) {
  return (
    <header className="flex flex-none items-center px-[30px] py-5">
      <button
        type="button"
        onClick={onHome}
        title={t.heroTitle}
        aria-label={t.heroTitle}
        className="flex items-center gap-[9px] rounded-lg transition-opacity hover:opacity-80 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
      >
        <Logo size={44} />
        <span className="text-[15px] font-bold tracking-[-0.2px] text-ink-800">MediSense</span>
      </button>

      <nav className="mx-auto hidden items-center gap-[30px] md:flex">
        {NAV_KEYS.map((key) => (
          <a
            key={key}
            href="#"
            onClick={(e) => e.preventDefault()}
            className="text-[13px] font-medium text-ink-600 transition-colors hover:text-ink-900"
          >
            {t[key]}
          </a>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-2 md:ml-0">
        <button
          type="button"
          onClick={onToggleLang}
          title={t.langTitle}
          aria-label={t.langTitle}
          className="flex items-center gap-[5px] rounded-[18px] border border-line-input bg-white px-[13px] py-[7px] text-[13px] font-semibold text-ink-700 transition-colors hover:bg-[#f0f1f3]"
        >
          <Globe size={15} strokeWidth={1.7} />
          {t.langBtn}
        </button>
        <button
          type="button"
          onClick={onSignIn}
          className="rounded-[18px] bg-[#0B0B0C] px-[18px] py-[7px] text-[13px] font-medium text-white transition-[filter] hover:brightness-125"
        >
          {t.signIn}
        </button>
      </div>
    </header>
  );
}
