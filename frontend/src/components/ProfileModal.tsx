import { useEffect } from "react";
import { X, User } from "lucide-react";
import type { Strings } from "../lib/i18n";
import type { AuthUser } from "../lib/api";

export default function ProfileModal({
  t,
  user,
  onClose,
}: {
  t: Strings;
  user: AuthUser;
  onClose: () => void;
}) {
  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const initials = user.name
    .split(/\s+/)
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  const rowCls = "flex items-center justify-between gap-4 py-[11px]";
  const keyCls = "text-[12.5px] font-medium text-ink-400";
  const valCls = "max-w-[220px] truncate text-[13.5px] font-semibold text-ink-900";

  return (
    <div
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={t.profile}
      className="fixed inset-0 z-50 flex animate-fade items-center justify-center bg-[rgba(15,23,42,0.34)] p-5 backdrop-blur-[3px]"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-[380px] animate-rise rounded-[18px] bg-white px-[26px] pb-[26px] pt-[28px] shadow-modal"
      >
        <div className="mb-1 flex items-center justify-end">
          <button
            type="button"
            onClick={onClose}
            title={t.close}
            aria-label={t.close}
            className="flex h-[30px] w-[30px] items-center justify-center rounded-full bg-[#F1F2F4] text-ink-500 transition-colors hover:bg-[#e6e8eb]"
          >
            <X size={16} strokeWidth={2} />
          </button>
        </div>

        <div className="mb-5 flex items-center gap-[14px]">
          <div className="flex h-[52px] w-[52px] flex-none items-center justify-center rounded-full bg-accent/10 text-[17px] font-bold text-accent">
            {initials || <User size={22} strokeWidth={1.8} />}
          </div>
          <div className="min-w-0">
            <h2 className="truncate text-[19px] font-bold tracking-[-0.3px] text-ink-900">
              {user.name}
            </h2>
            <p className="truncate text-[13px] text-ink-400">{user.email}</p>
          </div>
        </div>

        <div className="divide-y divide-line-input rounded-[12px] border border-line-input px-[15px]">
          <div className={rowCls}>
            <span className={keyCls}>{t.emailLabel}</span>
            <span className={valCls}>{user.email}</span>
          </div>
          <div className={rowCls}>
            <span className={keyCls}>{t.roleLabel}</span>
            <span className={`${valCls} capitalize`}>{user.role}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
