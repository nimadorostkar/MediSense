import { useEffect, useState } from "react";
import { X } from "lucide-react";
import type { Strings } from "../lib/i18n";
import { login, type AuthUser } from "../lib/api";

export default function LoginModal({
  t,
  onClose,
  onAuthed,
}: {
  t: Strings;
  onClose: () => void;
  onAuthed: (user: AuthUser) => void;
}) {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const isUp = mode === "signup";

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function submit() {
    if (busy) return;
    const validEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
    if (!validEmail) {
      setError(t.errEmail);
      return;
    }
    if (password.length < 6) {
      setError(t.errPass);
      return;
    }
    setError("");
    setBusy(true);
    try {
      // Authenticates against the backend (/api/auth/login) and stores the token.
      const user = await login(email.trim(), password);
      onAuthed(user);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : t.errAuth);
    } finally {
      setBusy(false);
    }
  }

  const inputCls =
    "w-full rounded-[10px] border border-line-input px-[13px] py-[11px] text-[14px] text-ink-900 outline-none transition-[border-color,box-shadow] focus:border-[#bfd0f7] focus:shadow-focus";
  const labelCls = "mb-[6px] block text-[12.5px] font-medium text-[#475569]";

  return (
    <div
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={isUp ? t.loginTitleUp : t.loginTitleIn}
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

        <h2 className="mb-1 mt-[14px] text-[20px] font-bold tracking-[-0.3px] text-ink-900">
          {isUp ? t.loginTitleUp : t.loginTitleIn}
        </h2>
        <p className="mb-5 text-[13.5px] text-ink-400">{isUp ? t.loginSubUp : t.loginSubIn}</p>

        <div className="mb-[14px]">
          <label htmlFor="ms-email" className={labelCls}>
            {t.emailLabel}
          </label>
          <input
            id="ms-email"
            type="email"
            autoComplete="email"
            autoFocus
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setError("");
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            placeholder={t.emailPh}
            className={inputCls}
          />
        </div>

        <div className="mb-2">
          <label htmlFor="ms-password" className={labelCls}>
            {t.passwordLabel}
          </label>
          <input
            id="ms-password"
            type="password"
            autoComplete={isUp ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setError("");
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="••••••••"
            className={inputCls}
          />
        </div>

        {error && (
          <div role="alert" className="mb-2 text-[12.5px] text-[#DC2626]">
            {error}
          </div>
        )}

        <button
          type="button"
          onClick={submit}
          disabled={busy}
          className="mt-[6px] w-full rounded-[10px] bg-accent p-3 text-[14px] font-semibold text-white transition-[filter] hover:brightness-110 disabled:opacity-60"
        >
          {busy ? t.signingIn : isUp ? t.ctaUp : t.ctaIn}
        </button>

        <div className="mt-4 text-center text-[12.5px] text-ink-400">
          {isUp ? t.switchUp : t.switchIn}{" "}
          <button
            type="button"
            onClick={() => {
              setMode(isUp ? "signin" : "signup");
              setError("");
            }}
            className="font-semibold text-accent hover:underline"
          >
            {isUp ? t.switchCtaUp : t.switchCtaIn}
          </button>
        </div>
      </div>
    </div>
  );
}
