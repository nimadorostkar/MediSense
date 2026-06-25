export type Lang = "en" | "zh";

export type Band = "High" | "Moderate" | "Low" | "Watch";

export interface DiffItem {
  condition: string;
  icd: string;
  probability: number;
  confidence: Band;
  because: string;
}

export interface Diagnosis {
  redFlag: string;
  summary: string;
  differential: DiffItem[];
  nextBestTest: string;
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
