export type Lang = "en" | "zh";

export type Band = "High" | "Moderate" | "Low" | "Watch";

export interface DiffItem {
  condition: string;
  icd: string;
  probability: number;
  confidence: Band;
  because: string;
}

export type Severity = "Contraindicated" | "Major" | "Moderate" | "Minor";

export interface SafetyFlag {
  severity: Severity;
  message: string;
}

export interface Medication {
  drug: string;
  dose?: string;
  route?: string;
  frequency?: string;
  duration?: string;
  note?: string;
}

export interface Treatment {
  bestDiagnosis: string;
  icd?: string;
  rationale?: string;
  plan?: string[];
  medications?: Medication[];
  safety?: SafetyFlag[];
  monitoring?: string;
  requiresPhysicianConfirmation?: boolean;
}

export interface Diagnosis {
  redFlag: string;
  summary: string;
  differential: DiffItem[];
  nextBestTest: string;
  /** Treatment plan + screened prescription, present once the doctor asks to treat. */
  treatment?: Treatment | null;
}

export interface Message {
  role: "doctor" | "ai";
  /** Doctor text, or AI raw fallback when structured parsing fails. */
  text?: string;
  /** Structured AI reply. */
  dx?: Diagnosis | null;
}

export interface Chat {
  id: string;
  title: string;
  messages: Message[];
}
