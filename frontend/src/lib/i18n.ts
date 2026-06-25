import type { Lang, Band } from "../types";

export interface Strings {
  // nav / header
  platform: string;
  solutions: string;
  evidence: string;
  integrations: string;
  pricing: string;
  signIn: string;
  signOut: string;
  signingIn: string;
  errAuth: string;
  engineError: string;
  langBtn: string;
  langTitle: string;
  // sidebar
  newChat: string;
  recent: string;
  noChats: string;
  collapse: string;
  showHistory: string;
  deleteChat: string;
  // hero
  heroTitle: string;
  heroSub: string;
  inputPh: string;
  chatPh: string;
  cDifferential: string;
  cDrugSafety: string;
  cTriage: string;
  cExplain: string;
  // ai card
  suggestion: string;
  nextBest: string;
  advisory: string;
  footer: string;
  // treatment card
  txTitle: string;
  txBest: string;
  txPlan: string;
  txMeds: string;
  txSafety: string;
  txMonitor: string;
  txClear: string;
  txConfirm: string;
  sevContra: string;
  sevMajor: string;
  sevModerate: string;
  sevMinor: string;
  // composer
  attach: string;
  micRec: string;
  micStop: string;
  send: string;
  // login
  emailLabel: string;
  passwordLabel: string;
  emailPh: string;
  loginTitleIn: string;
  loginTitleUp: string;
  loginSubIn: string;
  loginSubUp: string;
  ctaIn: string;
  ctaUp: string;
  switchIn: string;
  switchUp: string;
  switchCtaIn: string;
  switchCtaUp: string;
  errEmail: string;
  errPass: string;
  close: string;
  // confidence bands
  bandHigh: string;
  bandModerate: string;
  bandLow: string;
  bandWatch: string;
}

export const STRINGS: Record<Lang, Strings> = {
  en: {
    platform: "Platform",
    solutions: "Solutions",
    evidence: "Evidence",
    integrations: "Integrations",
    pricing: "Pricing",
    signIn: "Sign in",
    signOut: "Sign out",
    signingIn: "Signing in…",
    errAuth: "Sign-in failed. Check your credentials and that the backend is running.",
    engineError:
      "Couldn't reach the MediSense engine. No result is shown — please check the connection and try again.",
    langBtn: "中文",
    langTitle: "Switch language",
    newChat: "New chat",
    recent: "Recent",
    noChats: "No conversations yet.",
    collapse: "Collapse",
    showHistory: "Show history",
    deleteChat: "Delete conversation",
    heroTitle: "Your clinical assistant",
    heroSub: "Describe a patient and get a ranked differential — with the reasoning attached.",
    inputPh: "Describe the patient — symptoms, age, history, vitals…",
    chatPh: "Add more detail, ask a follow-up, or describe the next patient…",
    cDifferential: "Differential",
    cDrugSafety: "Drug safety",
    cTriage: "Triage",
    cExplain: "Explain",
    suggestion: "MediSense suggestion",
    nextBest: "Next best test —",
    advisory: "Advisory only — the physician confirms the final decision.",
    footer:
      "© 2026 MediSense · Decision support — the physician confirms every diagnosis and prescription.",
    txTitle: "Recommended plan",
    txBest: "Best-fit diagnosis",
    txPlan: "Plan",
    txMeds: "Medications",
    txSafety: "Drug-safety screen",
    txMonitor: "Monitoring",
    txClear: "No interactions or allergy conflicts found.",
    txConfirm: "Suggested plan — the physician confirms and signs before anything is prescribed.",
    sevContra: "Contraindicated",
    sevMajor: "Major",
    sevModerate: "Moderate",
    sevMinor: "Minor",
    attach: "Attach file",
    micRec: "Record voice",
    micStop: "Stop recording",
    send: "Send",
    emailLabel: "Email",
    passwordLabel: "Password",
    emailPh: "you@hospital.org",
    loginTitleIn: "Welcome back",
    loginTitleUp: "Create your account",
    loginSubIn: "Sign in to your MediSense workspace.",
    loginSubUp: "Start using MediSense clinical decision support.",
    ctaIn: "Sign in",
    ctaUp: "Create account",
    switchIn: "Don't have an account?",
    switchUp: "Already have an account?",
    switchCtaIn: "Sign up",
    switchCtaUp: "Sign in",
    errEmail: "Enter a valid email address.",
    errPass: "Password must be at least 6 characters.",
    close: "Close",
    bandHigh: "High",
    bandModerate: "Moderate",
    bandLow: "Low",
    bandWatch: "Watch",
  },
  zh: {
    platform: "平台",
    solutions: "解决方案",
    evidence: "循证",
    integrations: "集成",
    pricing: "定价",
    signIn: "登录",
    signOut: "退出",
    signingIn: "正在登录…",
    errAuth: "登录失败。请检查凭据并确认后端正在运行。",
    engineError: "无法连接 MediSense 引擎。未显示任何结果——请检查连接后重试。",
    langBtn: "EN",
    langTitle: "切换语言",
    newChat: "新对话",
    recent: "最近",
    noChats: "暂无对话。",
    collapse: "收起",
    showHistory: "显示历史",
    deleteChat: "删除对话",
    heroTitle: "您的临床智能助手",
    heroSub: "描述患者情况，即可获得带推理依据的鉴别诊断排序。",
    inputPh: "描述患者——症状、年龄、病史、生命体征……",
    chatPh: "补充细节、继续追问，或描述下一位患者……",
    cDifferential: "鉴别诊断",
    cDrugSafety: "用药安全",
    cTriage: "分诊",
    cExplain: "解释",
    suggestion: "MediSense 建议",
    nextBest: "建议下一步检查 —",
    advisory: "仅供参考——最终诊断由医生确认。",
    footer: "© 2026 MediSense · 临床决策支持——每项诊断与处方均由医生确认。",
    txTitle: "推荐方案",
    txBest: "最符合的诊断",
    txPlan: "处理方案",
    txMeds: "用药",
    txSafety: "用药安全筛查",
    txMonitor: "随访监测",
    txClear: "未发现药物相互作用或过敏冲突。",
    txConfirm: "建议方案——开具处方前须由医生确认并签署。",
    sevContra: "禁忌",
    sevMajor: "严重",
    sevModerate: "中度",
    sevMinor: "轻度",
    attach: "添加附件",
    micRec: "语音输入",
    micStop: "停止录音",
    send: "发送",
    emailLabel: "邮箱",
    passwordLabel: "密码",
    emailPh: "you@hospital.org",
    loginTitleIn: "欢迎回来",
    loginTitleUp: "创建账户",
    loginSubIn: "登录您的 MediSense 工作区。",
    loginSubUp: "开始使用 MediSense 临床决策支持。",
    ctaIn: "登录",
    ctaUp: "创建账户",
    switchIn: "还没有账户？",
    switchUp: "已有账户？",
    switchCtaIn: "注册",
    switchCtaUp: "登录",
    errEmail: "请输入有效的邮箱地址。",
    errPass: "密码至少需要 6 个字符。",
    close: "关闭",
    bandHigh: "高",
    bandModerate: "中",
    bandLow: "低",
    bandWatch: "警惕",
  },
};

export function bandLabel(band: Band, t: Strings): string {
  return (
    { High: t.bandHigh, Moderate: t.bandModerate, Low: t.bandLow, Watch: t.bandWatch }[band] ||
    band
  );
}
