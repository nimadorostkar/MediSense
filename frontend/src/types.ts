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
  /** KB safety alert level for this drug: RED / YELLOW / GREEN. */
  alert?: string;
  /** Insurance class from the KB (e.g. "Class B" / "乙类"). */
  insurance?: string;
  /** Contraindications listed in the KB (e.g. pregnancy). */
  contra?: string[];
  /** Required monitoring for this drug (e.g. "LFT, lipids q4w"). */
  monitor?: string;
}

/** A non-selected prescription tier from the KB, shown as an alternative. */
export interface TierOption {
  tier: string;
  medications: Medication[];
}

export interface Treatment {
  bestDiagnosis: string;
  icd?: string;
  rationale?: string;
  /** The prescription tier the severity selected (e.g. "topical mild"). */
  tier?: string;
  plan?: string[];
  medications?: Medication[];
  /** Every other prescription tier the database holds for this disease. */
  options?: TierOption[];
  /** Full patient-education list from the KB. */
  education?: string[];
  /** Follow-up schedule per severity from the KB. */
  followUp?: string[];
  safety?: SafetyFlag[];
  monitoring?: string;
  requiresPhysicianConfirmation?: boolean;
}

export interface Diagnosis {
  redFlag: string;
  summary: string;
  differential: DiffItem[];
  nextBestTest: string;
  /** Plan + screened prescription — attached to every supported diagnosis. */
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
