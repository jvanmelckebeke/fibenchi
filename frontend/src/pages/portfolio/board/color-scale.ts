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

// The day-adaptive scales below may only tighten over a board that was
// actually read. The max over a subset can never exceed the max over the whole
// set, so calibrating on the tiles that resolved returns a span at most as wide
// as the true one, and every tile that did resolve is painted louder than it
// is. A partial set can only ever over-tighten, whatever caused the blanks —
// which is why the gate is a coverage test and not a test of why a tile blanked.
//
// The threshold brackets the observed book: the normal state is 77 of 78
// scored (one warmup blank), while the two coverage collapses seen in practice
// left 18 of 70 and 43 of 78 with no reading — coverage 0.74 and 0.45. Any
// threshold above 0.74 and at or below 0.99 separates them.
//
// Freezing the scale at its canonical width outright is the obvious
// alternative and costs more than it saves: on a genuinely quiet, fully-read
// day the tightening is the only thing that gives relative outliers any colour
// at all. Gating it keeps the quiet day and disarms the adaptation only when
// the input cannot support it.
const TIGHTENING_COVERAGE = 0.9

/** Whether enough of the board resolved for the day-adaptive scales to tighten. */
export function hasTighteningCoverage(resolved: number, total: number): boolean {
  return resolved > 0 && resolved >= total * TIGHTENING_COVERAGE
}

/** σ-mode ramp unit adapted to the day's actual spread: on a quiet day the
 * scale tightens so relative outliers still get colour, but never below a
 * ±1.5σ full range (a dead-calm day must not scream) and never looser than
 * the canonical ±3σ. `total` is the tile count `sigmas` was read from. */
export function sigmaUnit(sigmas: number[], total: number): number {
  if (!hasTighteningCoverage(sigmas.length, total)) return 1
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

/** Day-adaptive span for %-of-today mode: tightens to the day's biggest move
 * but never below ±2% (a flat day must not scream) and never beyond ±7% (past
 * that, more red doesn't add information). `total` as in `sigmaUnit`. */
export function pctSpan(pcts: number[], total: number): number {
  if (!hasTighteningCoverage(pcts.length, total)) return 7
  const maxAbs = Math.max(...pcts.map(Math.abs))
  return Math.min(7, Math.max(2, maxAbs))
}

/** The tile fields the board's scale reads. Structural rather than an import
 * of `Tile`, because use-board-data imports this module. */
export interface ScaleTile {
  sigma: number | null
  todayPct: number | null
  reason: { kind: string } | null
}

/** The one ramp the whole board shares, over the *unfiltered* tile map: every
 * page and section paints on the same scale, and the tiles with no reading are
 * counted rather than dropped, since they decide whether it may tighten. */
export function boardScale(
  tiles: ScaleTile[],
  mode: ColorMode,
): { span: number; unread: number; pending: number; tightened: boolean } {
  const readings = tiles
    .map((t) => (mode === "sigma" ? t.sigma : t.todayPct))
    .filter((v): v is number => v != null)
  const pending = tiles.filter((t) => t.reason?.kind === "pending").length
  return {
    span:
      mode === "sigma"
        ? 3 * sigmaUnit(readings, tiles.length)
        : pctSpan(readings, tiles.length),
    unread: tiles.length - readings.length - pending,
    pending,
    tightened: hasTighteningCoverage(readings.length, tiles.length),
  }
}

/** Resolve a value to its tile colour + legible ink, interpolating linearly
 * along the ramp across ±span (σ: 3 × sigmaUnit; %: pctSpan — both
 * day-adaptive). Values beyond the span clamp to the end colours. */
export function rampColor(value: number, span: number): { color: string; ink: string } {
  const t = Math.max(-1, Math.min(1, span === 0 ? 0 : value / span))
  const p = (t + 1) * ((RAMP_COLORS.length - 1) / 2) // 0 … 6 across the stops
  const i = Math.min(RAMP_COLORS.length - 2, Math.floor(p))
  const color = lerpHex(RAMP_COLORS[i], RAMP_COLORS[i + 1], p - i)
  return { color, ink: readableTextColor(color) }
}

/** The σ-Move EWMA baseline length: bars needed before the vol forecast is
 * trustworthy. Mirrors the backend vnr registry warmup (60 sessions). */
export const VNR_BASELINE_SESSIONS = 60
