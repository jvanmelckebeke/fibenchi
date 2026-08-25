// Baseline selection for the board's %-over-a-window readings.
//
// A window return is `(last - baseline) / baseline`, where the baseline is the
// close the window starts from. The subtlety is entirely in picking it: the
// series the board holds is fetched over the widest window (1mo), so the widest
// window's start is also the series' first day. Requiring a close at or before
// that day means the reading exists only when that one calendar day happens to
// be a trading session — two days in seven it is a weekend and every tile's
// 1mo reading blanks at once.
//
// So a window start that lands inside a market closure takes the first close
// after it. The grace is bounded: a series that begins mid-window because the
// asset was added recently starts much further in than any closure run, and
// still has no baseline — which is the honest answer for it.

import { type SparklinePoint } from "@/lib/api"
import { relativeStart } from "@/lib/asset-window"
import { PCT_WINDOWS, type PctWindow } from "./color-scale"

/** How far past a window's start a baseline may sit and still count. Covers the
 * longest run of consecutive closed sessions a window can open on — a weekend
 * with public holidays on both shoulders. */
const BASELINE_GRACE_DAYS = 5

export interface WindowBounds {
  /** ISO date the window opens on. */
  start: string
  /** Latest ISO date a close may carry and still serve as this window's baseline. */
  latestBaseline: string
}

/** The bounds of each board window, relative to today's local date. */
export function windowCutoffs(): Record<PctWindow, WindowBounds> {
  const out = {} as Record<PctWindow, WindowBounds>
  for (const w of PCT_WINDOWS) {
    out[w.value] = {
      start: relativeStart(w.days),
      latestBaseline: relativeStart(w.days - BASELINE_GRACE_DAYS),
    }
  }
  return out
}

/**
 * Percent change from the window's baseline close to `last`, or null when the
 * series carries no close the window can start from.
 *
 * `points` must be ascending by date.
 */
export function windowPct(
  points: SparklinePoint[],
  last: number,
  bounds: WindowBounds,
): number | null {
  if (!points.length) return null

  let base: SparklinePoint | null = null
  for (const p of points) {
    if (p.date <= bounds.start) base = p
    else break
  }
  // Nothing on or before the start: the window opened while the venue was
  // closed, so the session that reopened it is the baseline.
  if (!base && points[0].date <= bounds.latestBaseline) base = points[0]

  if (!base || base.close === 0) return null
  return ((last - base.close) / base.close) * 100
}
