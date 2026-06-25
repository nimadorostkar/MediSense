# MediSense — React + Vite + TypeScript

A clinical decision-support chat UI for physicians. A doctor describes a patient
(typed or dictated) and receives a ranked differential diagnosis with the
reasoning attached. English / Simplified Chinese.

> Decision support only — illustrative. The physician confirms every diagnosis
> and prescription.

## Stack

- **React 18 + Vite 5 + TypeScript** (strict, project references)
- **Tailwind CSS 3** for styling (design tokens in `tailwind.config.js`)
- **lucide-react** for icons
- **Web Speech API** for voice dictation
- A tiny **Express** route that keeps the Anthropic API key server-side

## Quick start

```bash
cd app
npm install
npm run dev
```

Open the printed `localhost` URL. Out of the box the UI runs with an **offline
demo reply** so you can click through every state without a key.

## Get real clinical reasoning

The model is called from the server so the API key never reaches the browser.

```bash
cp .env.example .env
# edit .env -> ANTHROPIC_API_KEY=sk-ant-...

npm run server   # terminal 1 — API on :8787
npm run dev      # terminal 2 — Vite proxies /api -> :8787
```

In dev, `vite.config.ts` proxies `/api` to the server. In production, build the
frontend and let the same server host it:

```bash
npm run build    # outputs dist/
npm run server   # serves dist/ + the /api/clinical route
```

## How the AI contract works

`src/lib/api.ts` posts the conversation to `POST /api/clinical`. The model is
instructed to return **only** a JSON object:

```ts
{
  redFlag: string,
  summary: string,
  differential: [
    { condition, icd, probability /* 0–100 */, confidence: "High"|"Moderate"|"Low"|"Watch", because }
  ],
  nextBestTest: string
}
```

`parseReply()` extracts it defensively (strips code fences, grabs the `{…}`
substring, `try/catch`). If parsing fails, the raw text renders as a plain
assistant bubble. `normBand()` normalizes confidence to the four bands. When the
UI language is Chinese, the model is told to write every string value in
Simplified Chinese (confidence enum + ICD codes stay as-is).

Confidence bands map to colors: **High = blue, Moderate = amber, Low = gray,
Watch = red.**

## Project structure

```
app/
  index.html
  vite.config.ts            Dev server + /api proxy + build config
  tailwind.config.js        Design tokens, keyframes (logo sprite, fades)
  postcss.config.js
  .env.example
  server/
    index.js                Express route -> Anthropic (key stays here)
  src/
    main.tsx
    App.tsx                 Orchestration: messages, language, sidebar, login
    index.css               Tailwind layers + sprite/scrollbar helpers
    types.ts                Shared types
    vite-env.d.ts
    lib/
      i18n.ts               English + Chinese tables, confidence labels
      api.ts                Prompt builder, JSON parser, band normalizer, fetch + demo stub
      bands.ts              Confidence-band color palettes
    hooks/
      useChats.ts           Chat history (localStorage)
      useSpeech.ts          Web Speech API dictation
    components/
      Header.tsx            Logo, nav, language toggle, Sign in
      Sidebar.tsx           Collapsible chat history
      HeroInput.tsx         Empty-state hero + quick-action chips
      Composer.tsx          Textarea + paperclip + mic + send
      MessageList.tsx       Message bubbles + thinking indicator
      DifferentialCard.tsx  Structured AI card (red flag, ranked differential, next test)
      LoginModal.tsx        Email/password sign in / sign up with validation
      Logo.tsx              Animated 46-frame sprite logo
  public/
    logo-sphere.png         46-frame horizontal sprite strip (7820×170)
```

## Notes

- Chat history is the only persisted state (`localStorage` key `medisense_chats`).
- Voice dictation needs a SpeechRecognition-capable browser (Chrome/Edge); the
  mic button hides itself where unsupported. Language follows the UI (zh-CN / en-US).
- Accessible: labelled controls, focus rings, 44px+ hit targets, Escape/backdrop
  to close the modal.
- This is illustrative decision support — not a medical device.
```
