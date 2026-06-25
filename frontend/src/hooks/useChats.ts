import { useCallback, useEffect, useState } from "react";
import type { Chat, Message } from "../types";

const KEY = "medisense_chats";

function titleFrom(text: string): string {
  const t = (text || "").replace(/\s+/g, " ").trim();
  return t.length > 34 ? t.slice(0, 34) + "…" : t || "New chat";
}

/** Chat-history state persisted to localStorage. */
export function useChats() {
  const [chats, setChats] = useState<Chat[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) setChats(parsed);
      }
    } catch {
      /* ignore corrupt storage */
    }
  }, []);

  const persist = useCallback((next: Chat[]) => {
    try {
      localStorage.setItem(KEY, JSON.stringify(next));
    } catch {
      /* storage may be full or blocked */
    }
  }, []);

  /** Ensure there's an active chat for this message; returns its id. */
  const upsert = useCallback(
    (messages: Message[], firstText: string): string => {
      let id = activeId;
      setChats((prev) => {
        let next: Chat[];
        if (!id) {
          id = "c" + Date.now();
          next = [{ id, title: titleFrom(firstText), messages }, ...prev];
        } else {
          next = prev.map((c) => (c.id === id ? { ...c, messages } : c));
        }
        persist(next);
        return next;
      });
      if (!activeId) setActiveId(id);
      return id!;
    },
    [activeId, persist]
  );

  const updateMessages = useCallback(
    (id: string, messages: Message[]) => {
      setChats((prev) => {
        const next = prev.map((c) => (c.id === id ? { ...c, messages } : c));
        persist(next);
        return next;
      });
    },
    [persist]
  );

  const remove = useCallback(
    (id: string) => {
      setChats((prev) => {
        const next = prev.filter((c) => c.id !== id);
        persist(next);
        return next;
      });
      setActiveId((cur) => (cur === id ? null : cur));
    },
    [persist]
  );

  return { chats, activeId, setActiveId, upsert, updateMessages, remove };
}
