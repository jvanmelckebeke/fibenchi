// Where a window move sits in the symbol's own history of moves over that
// window: the share of past moves that were smaller in absolute size. The
// backend ships the history as 21 quantiles (p = 0, 5, ..., 100), and the live
// move is placed on the piecewise-linear curve through them.

import type { MoveScale } from "@/lib/api"

const STEP = 0.05

/** Percentile in [0, 1] of `|movePct|` on `quantiles`. Below the smallest
 * quantile is 0, at or above the largest is 1. Where adjacent quantiles are
 * equal the upper index wins, so a move equal to a run of tied quantiles reads
 * as the top of the run. */
export function movePercentile(movePct: number, quantiles: MoveScale["quantiles"]): number {
  const x = Math.abs(movePct)
  const last = quantiles.length - 1
  if (last < 0 || x < quantiles[0]) return 0
  if (x >= quantiles[last]) return 1
  // Largest i with quantiles[i] <= x. It is below `last`, so i + 1 exists and
  // quantiles[i + 1] > x >= quantiles[i].
  let i = 0
  while (quantiles[i + 1] <= x) i++
  const lo = quantiles[i]
  const hi = quantiles[i + 1]
  return Math.min(1, Math.max(0, (i + (x - lo) / (hi - lo)) * STEP))
}

/** The shortest fill a tile's window bar draws for a real reading. Without it a
 * move at the bottom of its history would draw nothing, and look like the empty
 * track that means there is no reading at all. */
export const MIN_WINDOW_FILL = 0.12

/** Fill of a tile's window bar, 0..1, or null for an empty track: no move, or
 * too little history to say how unusual it is. */
export function windowBarFill(percentile: number | null): number | null {
  return percentile == null ? null : Math.max(MIN_WINDOW_FILL, percentile)
}

/** Width of a Movers row's background bar in percent. No scale, no bar. */
export function moverBarWidth(percentile: number | null): number {
  return percentile == null ? 0 : percentile * 100
}
