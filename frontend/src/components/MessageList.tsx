import { useEffect, useRef } from "react";
import type { Message } from "../types";
import type { Strings } from "../lib/i18n";
import DifferentialCard from "./DifferentialCard";

export default function MessageList({
  messages,
  thinking,
  t,
}: {
  messages: Message[];
  thinking: boolean;
  t: Strings;
}) {
  const ref = useRef<HTMLDivElement>(null);

  // Keep the latest message in view.
  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, thinking]);

  return (
    <div
      ref={ref}
      className="ms-scroll flex flex-1 flex-col gap-4 overflow-y-auto px-[2px] py-[22px]"
    >
      {messages.map((m, i) =>
        m.role === "ai" ? (
          <div key={i} className="flex animate-rise justify-start">
            <DifferentialCard msg={m} t={t} />
          </div>
        ) : (
          <div key={i} className="flex animate-rise justify-end">
            <div className="max-w-[82%] whitespace-pre-wrap rounded-[16px_16px_4px_16px] bg-accent px-4 py-3 text-[14.5px] leading-[1.6] text-white">
              {m.text}
            </div>
          </div>
        )
      )}

      {thinking && (
        <div className="flex gap-[5px] self-start rounded-[4px_16px_16px_16px] border border-line bg-white px-[18px] py-[14px]">
          {[0, 0.2, 0.4].map((d) => (
            <span
              key={d}
              className="h-[7px] w-[7px] rounded-full bg-accent"
              style={{ animation: `blink 1.2s infinite ${d}s` }}
            />
          ))}
        </div>
      )}
    </div>
  );
}
