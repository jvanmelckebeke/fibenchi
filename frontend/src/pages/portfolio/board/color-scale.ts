// The board's diverging colour ramp and its scaling rules.
//
// A continuous two-hue diverging scale through a neutral grey midpoint, so
// "nothing happened" reads as nothing and ±0.7σ vs ±0.8σ differ by a shade,
// not a cliff. The no-reading state is deliberately NOT on this ramp
// (design principle 1: unknown must never render as calm).

import { readableTextColor } from "@/lib/format"

// Gradient stops at -3 … +3 (×unit): deep red → neutral grey → bright green.
export const RAMP_COLORS = [
  "#7f1d2b",
  "#a8323f",
  "#c2666e",
  "#3b3b40",
  "#4f8f6d",
  "#3fa878",
  "#2fc98a",
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
 * scale tightens so relative outliers still get colour, but never below a
 * ±1.5σ full range (a dead-calm day must not scream) and never looser than
 * the canonical ±3σ. The legend prints the resulting range, so the scale
 * stays honest about what it's doing. */
export function sigmaUnit(sigmas: number[]): number {
  if (!sigmas.length) return 1
  const maxAbs = Math.max(...sigmas.map(Math.abs))
  return Math.min(1, Math.max(0.5, maxAbs / 3))
}

function hexToRgb(hex: string): [number, number, number] {
  const h = hex.slice(1)
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]
}

function lerpHex(a: string, b: string, t: number): string {
  const ca = hexToRgb(a)
  const cb = hexToRgb(b)
  const c = ca.map((v, i) => Math.round(v + (cb[i] - v) * t))
  return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`
}

/** Resolve a value to its tile colour + legible ink, interpolating linearly
 * along the ramp. σ mode spans ±3 × the day-adaptive `unit` (see sigmaUnit);
 * % mode spans the window's expected range (a fixed scale would render a
 * month as all-extremes). Values beyond the span clamp to the end colours. */
export function rampColor(
  value: number,
  mode: ColorMode,
  window?: PctWindow,
  unit = 1,
): { color: string; ink: string } {
  const span = mode === "sigma" ? 3 * unit : pctWindowDef(window ?? "1wk").maxAbs
  const t = Math.max(-1, Math.min(1, span === 0 ? 0 : value / span))
  const p = (t + 1) * ((RAMP_COLORS.length - 1) / 2) // 0 … 6 across the stops
  const i = Math.min(RAMP_COLORS.length - 2, Math.floor(p))
  const color = lerpHex(RAMP_COLORS[i], RAMP_COLORS[i + 1], p - i)
  return { color, ink: readableTextColor(color) }
}

/** The σ-Move EWMA baseline length: bars needed before the vol forecast is
 * trustworthy. Mirrors the backend vnr registry warmup (60 sessions). */
export const VNR_BASELINE_SESSIONS = 60
