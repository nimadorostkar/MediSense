import { useEffect, useRef, useState } from "react";
import { Globe, LogOut, FlaskConical, User, ChevronDown, Menu, X } from "lucide-react";
import type { Strings } from "../lib/i18n";
import type { AuthUser } from "../lib/api";
import Logo from "./Logo";

export default function Header({
  t,
  user,
  demoMode = false,
  onToggleLang,
  onSignIn,
  onSignOut,
  onProfile,
  onHome,
}: {
  t: Strings;
  user: AuthUser | null;
  demoMode?: boolean;
  aiChat?: boolean;
  aiProvider?: string | null;
  onToggleLang: () => void;
  onSignIn: () => void;
  onSignOut: () => void;
  onProfile: () => void;
  onHome: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const navRef = useRef<HTMLDivElement>(null);

  // Close the account menu on outside click or Escape.
  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  // Close the mobile nav on outside click or Escape.
  useEffect(() => {
    if (!navOpen) return;
    const onDown = (e: MouseEvent) => {
      if (navRef.current && !navRef.current.contains(e.target as Node)) setNavOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setNavOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [navOpen]);

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

      {/* Desktop: buttons inline */}
      <div className="ml-auto hidden items-start gap-2 md:flex">
        {demoMode && (
          <span
            title={t.demoBadgeTitle}
            className="flex items-center gap-[5px] rounded-[18px] border border-amber-300 bg-amber-50 px-[11px] py-[7px] text-[12px] font-semibold text-amber-700"
          >
            <FlaskConical size={14} strokeWidth={1.8} />
            {t.demoBadge}
          </span>
        )}
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
        {user ? (
          <div ref={menuRef} className="relative">
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              aria-haspopup="menu"
              aria-expanded={menuOpen}
              className="flex max-w-[200px] items-center gap-[5px] rounded-[18px] border border-line-input bg-white px-[13px] py-[7px] text-[13px] font-semibold text-ink-700 transition-colors hover:bg-[#f0f1f3]"
            >
              <User size={15} strokeWidth={1.7} />
              <span className="truncate">{user.name}</span>
              <ChevronDown
                size={14}
                strokeWidth={1.9}
                className={`transition-transform ${menuOpen ? "rotate-180" : ""}`}
              />
            </button>

            {menuOpen && (
              <div
                role="menu"
                className="absolute right-0 z-50 mt-[7px] w-[190px] animate-fade overflow-hidden rounded-[12px] border border-line-input bg-white py-[6px] shadow-modal"
              >
                <div className="border-b border-line-input px-[13px] pb-[9px] pt-[5px]">
                  <div className="truncate text-[13px] font-semibold text-ink-900">{user.name}</div>
                  <div className="truncate text-[11.5px] text-ink-400">{user.email}</div>
                </div>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false);
                    onProfile();
                  }}
                  className="flex w-full items-center gap-[9px] px-[13px] py-[9px] text-left text-[13px] font-medium text-ink-700 transition-colors hover:bg-[#f0f1f3]"
                >
                  <User size={15} strokeWidth={1.7} />
                  {t.profile}
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setMenuOpen(false);
                    onSignOut();
                  }}
                  className="flex w-full items-center gap-[9px] px-[13px] py-[9px] text-left text-[13px] font-medium text-[#DC2626] transition-colors hover:bg-[#fdecec]"
                >
                  <LogOut size={15} strokeWidth={1.7} />
                  {t.logout}
                </button>
              </div>
            )}
          </div>
        ) : (
          <button
            type="button"
            onClick={onSignIn}
            className="rounded-[18px] bg-[#0B0B0C] px-[18px] py-[7px] text-[13px] font-medium text-white transition-[filter] hover:brightness-125"
          >
            {t.signIn}
          </button>
        )}
      </div>

      {/* Mobile: everything collapses into a hamburger menu */}
      <div ref={navRef} className="relative ml-auto md:hidden">
        <button
          type="button"
          onClick={() => setNavOpen((o) => !o)}
          aria-haspopup="menu"
          aria-expanded={navOpen}
          aria-label={t.menu}
          title={t.menu}
          className="flex h-[38px] w-[38px] items-center justify-center rounded-[12px] border border-line-input bg-white text-ink-700 transition-colors hover:bg-[#f0f1f3]"
        >
          {navOpen ? <X size={18} strokeWidth={1.9} /> : <Menu size={18} strokeWidth={1.9} />}
        </button>

        {navOpen && (
          <div
            role="menu"
            className="absolute right-0 z-50 mt-[9px] w-[220px] animate-fade overflow-hidden rounded-[12px] border border-line-input bg-white py-[6px] shadow-modal"
          >
            {user && (
              <div className="border-b border-line-input px-[14px] pb-[9px] pt-[5px]">
                <div className="truncate text-[13px] font-semibold text-ink-900">{user.name}</div>
                <div className="truncate text-[11.5px] text-ink-400">{user.email}</div>
              </div>
            )}

            {demoMode && (
              <div className="flex items-center gap-[9px] px-[14px] py-[9px] text-[13px] font-semibold text-amber-700">
                <FlaskConical size={15} strokeWidth={1.8} />
                {t.demoBadge}
              </div>
            )}

            <button
              type="button"
              role="menuitem"
              onClick={() => {
                setNavOpen(false);
                onToggleLang();
              }}
              className="flex w-full items-center gap-[9px] px-[14px] py-[9px] text-left text-[13px] font-medium text-ink-700 transition-colors hover:bg-[#f0f1f3]"
            >
              <Globe size={15} strokeWidth={1.7} />
              {t.langBtn}
            </button>

            {user ? (
              <>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setNavOpen(false);
                    onProfile();
                  }}
                  className="flex w-full items-center gap-[9px] px-[14px] py-[9px] text-left text-[13px] font-medium text-ink-700 transition-colors hover:bg-[#f0f1f3]"
                >
                  <User size={15} strokeWidth={1.7} />
                  {t.profile}
                </button>
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    setNavOpen(false);
                    onSignOut();
                  }}
                  className="flex w-full items-center gap-[9px] px-[14px] py-[9px] text-left text-[13px] font-medium text-[#DC2626] transition-colors hover:bg-[#fdecec]"
                >
                  <LogOut size={15} strokeWidth={1.7} />
                  {t.logout}
                </button>
              </>
            ) : (
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  setNavOpen(false);
                  onSignIn();
                }}
                className="mx-[10px] my-[5px] flex items-center justify-center rounded-[10px] bg-[#0B0B0C] px-[14px] py-[9px] text-[13px] font-medium text-white transition-[filter] hover:brightness-125"
                style={{ width: "calc(100% - 20px)" }}
              >
                {t.signIn}
              </button>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
