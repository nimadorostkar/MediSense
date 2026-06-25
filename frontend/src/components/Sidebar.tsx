import { Plus, MessageSquare, Trash2, ChevronLeft } from "lucide-react";
import type { Chat } from "../types";
import type { Strings } from "../lib/i18n";

export default function Sidebar({
  t,
  chats,
  activeId,
  onNew,
  onSelect,
  onDelete,
  onCollapse,
}: {
  t: Strings;
  chats: Chat[];
  activeId: string | null;
  onNew: () => void;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onCollapse: () => void;
}) {
  return (
    <aside className="flex w-[236px] flex-none flex-col border-r border-line-soft bg-[#FBFBFC]">
      <div className="px-[14px] pb-[10px] pt-4">
        <button
          type="button"
          onClick={onNew}
          className="flex w-full items-center justify-center gap-[7px] rounded-[10px] border border-line-input bg-white p-[10px] text-[13.5px] font-semibold text-ink-900 transition-colors hover:bg-[#f6f7f9]"
        >
          <Plus size={15} strokeWidth={2} />
          {t.newChat}
        </button>
      </div>

      <div className="px-4 py-[6px] text-[11px] font-semibold uppercase tracking-[0.5px] text-ink-200">
        {t.recent}
      </div>

      <div className="ms-scroll flex flex-1 flex-col gap-[2px] overflow-y-auto px-2 pb-[14px]">
        {chats.length === 0 && (
          <div className="px-3 py-[10px] text-[12.5px] text-[#A8AEB6]">{t.noChats}</div>
        )}
        {chats.map((c) => {
          const active = c.id === activeId;
          return (
            <div
              key={c.id}
              onClick={() => onSelect(c.id)}
              className={`group flex cursor-pointer items-center gap-[9px] rounded-[9px] px-[10px] py-[9px] text-[13px] text-ink-900 transition-colors hover:bg-[#f0f1f3] ${
                active ? "bg-accent-soft font-semibold" : "font-normal"
              }`}
            >
              <MessageSquare size={15} strokeWidth={1.6} className="flex-none opacity-65" />
              <span className="flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
                {c.title}
              </span>
              <button
                type="button"
                title={t.deleteChat}
                aria-label={t.deleteChat}
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(c.id);
                }}
                className="flex flex-none items-center p-0 text-[#94A3B8] opacity-0 transition-opacity hover:text-[#dc2626] group-hover:opacity-100"
              >
                <Trash2 size={14} strokeWidth={1.7} />
              </button>
            </div>
          );
        })}
      </div>

      <div className="flex-none border-t border-line-soft px-[14px] pb-[14px] pt-[10px]">
        <button
          type="button"
          onClick={onCollapse}
          className="flex w-full items-center justify-center gap-2 rounded-[10px] border border-line-input bg-white p-[9px] text-[12.5px] font-medium text-ink-600 transition-colors hover:bg-[#f0f1f3]"
        >
          <ChevronLeft size={16} strokeWidth={1.7} />
          {t.collapse}
        </button>
      </div>
    </aside>
  );
}
