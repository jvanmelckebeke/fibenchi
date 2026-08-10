// The board's diverging colour ramp and its bucketing rules.
//
// Seven classes, two opposed hues with a neutral grey midpoint so "nothing
// happened" reads as nothing. The no-reading state is deliberately NOT on
// this ramp (design principle 1: unknown must never render as calm).

export interface RampStop {
  color: string
  /** Ink colour that stays legible on this swatch. */
  ink: string
  label: string
}

// ≤-3σ … ≥+3σ. Inks picked per swatch: the outer reds/greens are dark enough
// for near-white, the mid stops need brighter contrast handling.
export const RAMP: RampStop[] = [
  { color: "#7f1d2b", ink: "#f5e3e5", label: "≤ -3" },
  { color: "#a8323f", ink: "#f8e7e9", label: "-3 … -2" },
  { color: "#c2666e", ink: "#2b1114", label: "-2 … -1" },
  { color: "#3b3b40", ink: "#c9c9cf", label: "-1 … +1" },
  { color: "#4f8f6d", ink: "#0e1f17", label: "+1 … +2" },
  { color: "#3fa878", ink: "#0c2018", label: "+2 … +3" },
  { color: "#2fc98a", ink: "#0a2318", label: "≥ +3" },
]

export type ColorMode = "sigma" | "pct"
export type PctWindow = "1wk" | "2wk" | "1mo"

export const PCT_WINDOWS: { value: PctWindow; label: string; days: number; maxAbs: number }[] = [
  { value: "1wk", label: "1 week", days: 7, maxAbs: 7 },
  { value: "2wk", label: "2 weeks", days: 14, maxAbs: 10 },
  { value: "1mo", label: "1 month", days: 30, maxAbs: 14 },
]

export function pctWindowDef(w: PctWindow) {
  return PCT_WINDOWS.find((d) => d.value === w) ?? PCT_WINDOWS[0]
}

/** σ-mode ramp unit adapted to the day's actual spread: on a quiet day the
 * edges tighten so relative outliers still get colour, but never below a
 * ±1.5σ full range (a dead-calm day must not scream) and never looser than
 * the canonical ±3σ. The legend prints the resulting range, so the scale
 * stays honest about what it's doing. */
export function sigmaUnit(sigmas: number[]): number {
  if (!sigmas.length) return 1
  const maxAbs = Math.max(...sigmas.map(Math.abs))
  return Math.min(1, Math.max(0.5, maxAbs / 3))
}

/** Bucket a value into the 7-class ramp. σ mode uses ±1/2/3 edges scaled by
 * the day-adaptive `unit` (see sigmaUnit); % mode rescales the same edges to
 * the window's expected range (a fixed scale would render a month as
 * all-extremes). */
export function rampStop(
  value: number,
  mode: ColorMode,
  window?: PctWindow,
  unit = 1,
): RampStop {
  const scale = mode === "sigma" ? unit : pctWindowDef(window ?? "1wk").maxAbs / 3
  const edges = [-3, -2, -1, 1, 2, 3].map((e) => e * scale)
  let idx = 0
  while (idx < edges.length && value >= edges[idx]) idx++
  return RAMP[idx]
}

/** The σ-Move EWMA baseline length: bars needed before the vol forecast is
 * trustworthy. Mirrors the backend vnr registry warmup (60 sessions). */
export const VNR_BASELINE_SESSIONS = 60
