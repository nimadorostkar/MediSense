import { useMemo, useState } from "react";
import { PanelLeft } from "lucide-react";
import type { Lang, Message } from "./types";
import { STRINGS } from "./lib/i18n";
import { clinicalComplete, parseReply } from "./lib/api";
import { useChats } from "./hooks/useChats";
import { useSpeech } from "./hooks/useSpeech";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import Composer from "./components/Composer";
import MessageList from "./components/MessageList";
import LoginModal from "./components/LoginModal";
import HeroInput, { CHIP_ICONS, type Chip } from "./components/HeroInput";

const SAMPLES = {
  dx: "62F, 3 days of fever, productive cough and right-sided pleuritic chest pain. RR 22, SpO2 94%. Give me a ranked differential.",
  rx: "Patient on warfarin and metformin, eGFR 48. I want to add an antibiotic for a chest infection — what is safe?",
  triage:
    "67M, central chest pain radiating to left arm, diaphoretic. HR 118, BP 92/60. How urgent is this?",
  explain:
    "For the pneumonia suggestion above, explain why it is ranked first and what would change it.",
};

export default function App() {
  const [lang, setLang] = useState<Lang>("en");
  const t = STRINGS[lang];

  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const [started, setStarted] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [showLogin, setShowLogin] = useState(false);

  const { chats, activeId, setActiveId, upsert, updateMessages, remove } = useChats();
  const { recording, supported: micSupported, toggle } = useSpeech(lang, (v) => setDraft(v));

  async function send() {
    const text = draft.trim();
    if (!text || thinking) return;

    const history: Message[] = [...messages, { role: "doctor", text }];
    setMessages(history);
    setDraft("");
    setStarted(true);
    setThinking(true);

    const id = upsert(history, text);

    let reply = "";
    try {
      reply = await clinicalComplete(history, lang);
    } catch {
      reply = "";
    }
    const parsed = parseReply(reply);
    const fallback = parsed
      ? ""
      : reply.trim() ||
        "I couldn't reach the reasoning engine just now. Please try again in a moment.";
    const finalMsgs: Message[] = [...history, { role: "ai", dx: parsed, text: fallback }];
    setMessages(finalMsgs);
    setThinking(false);
    updateMessages(id, finalMsgs);
  }

  function newChat() {
    setMessages([]);
    setActiveId(null);
    setStarted(false);
    setDraft("");
  }

  function selectChat(id: string) {
    const c = chats.find((x) => x.id === id);
    if (!c) return;
    setActiveId(id);
    setMessages(c.messages);
    setStarted(c.messages.length > 0);
    setDraft("");
  }

  const chips = useMemo<Chip[]>(
    () => [
      { label: t.cDifferential, sample: SAMPLES.dx, icon: CHIP_ICONS.Activity },
      { label: t.cDrugSafety, sample: SAMPLES.rx, icon: CHIP_ICONS.ShieldCheck },
      { label: t.cTriage, sample: SAMPLES.triage, icon: CHIP_ICONS.Clock },
      { label: t.cExplain, sample: SAMPLES.explain, icon: CHIP_ICONS.MessageCircle },
    ],
    [t]
  );

  return (
    <div className="min-h-screen bg-canvas p-4">
      <div className="mx-auto flex min-h-[calc(100vh-32px)] max-w-[1280px] flex-col overflow-hidden rounded-card border border-[#EBECEE] bg-gradient-to-b from-[#FCFCFD] to-[#F5F6F7] shadow-card">
        <Header
          t={t}
          onToggleLang={() => setLang(lang === "en" ? "zh" : "en")}
          onSignIn={() => setShowLogin(true)}
        />

        <div className="flex min-h-0 flex-1">
          {sidebarOpen && (
            <Sidebar
              t={t}
              chats={chats}
              activeId={activeId}
              onNew={newChat}
              onSelect={selectChat}
              onDelete={remove}
              onCollapse={() => setSidebarOpen(false)}
            />
          )}

          <div className="relative flex min-h-0 flex-1 flex-col">
            {!sidebarOpen && (
              <div className="absolute bottom-[18px] left-6 z-[5]">
                <button
                  type="button"
                  onClick={() => setSidebarOpen(true)}
                  title={t.showHistory}
                  aria-label={t.showHistory}
                  className="flex items-center rounded-[9px] border border-line-input bg-white p-[7px] text-ink-600 shadow-iconbtn transition-colors hover:bg-[#f0f1f3] hover:text-ink-900"
                >
                  <PanelLeft size={17} strokeWidth={1.7} />
                </button>
              </div>
            )}

            <main className="flex min-h-0 flex-1 flex-col px-[30px]">
              {!started ? (
                <HeroInput
                  t={t}
                  draft={draft}
                  onChange={setDraft}
                  onSend={send}
                  recording={recording}
                  micSupported={micSupported}
                  onMic={() => toggle(draft)}
                  chips={chips}
                />
              ) : (
                <div className="mx-auto flex min-h-0 w-full max-w-[760px] flex-1 flex-col">
                  <MessageList messages={messages} thinking={thinking} t={t} />
                  <Composer
                    t={t}
                    value={draft}
                    onChange={setDraft}
                    onSend={send}
                    placeholder={t.chatPh}
                    recording={recording}
                    micSupported={micSupported}
                    onMic={() => toggle(draft)}
                    card={false}
                  />
                </div>
              )}
            </main>

            <footer className="flex-none px-4 py-[18px] text-center text-[12px] text-ink-200">
              {t.footer}
            </footer>
          </div>
        </div>
      </div>

      {showLogin && <LoginModal t={t} onClose={() => setShowLogin(false)} />}
    </div>
  );
}
