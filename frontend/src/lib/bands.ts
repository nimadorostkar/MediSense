import type { Band } from "../types";

export interface BandPalette {
  /** Probability-bar fill color. */
  bar: string;
  /** Badge background. */
  bg: string;
  /** Badge text color. */
  fg: string;
}

const ACCENT = "#2563EB";

/** Confidence-band → colors. High=blue, Moderate=amber, Low=gray, Watch=red. */
export function bandPalette(band: Band): BandPalette {
  switch (band) {
    case "High":
      return { bar: ACCENT, bg: "rgba(37,99,235,0.12)", fg: ACCENT };
    case "Moderate":
      return { bar: "#D97706", bg: "#FEF3E2", fg: "#B45309" };
    case "Watch":
      return { bar: "#DC2626", bg: "#FEECEC", fg: "#DC2626" };
    case "Low":
    default:
      return { bar: "#CBD5E1", bg: "#F1F3F5", fg: "#64748B" };
  }
}
