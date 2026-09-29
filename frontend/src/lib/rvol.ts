/**
 * Relative volume resolution — the one place that decides what the RVOL column
 * shows.
 *
 * RVOL asks "is today heavy?", and the stored answer is about yesterday: it
 * divides a *settled* daily bar's volume by the 20-day average, and price-sync
 * discards the session still forming. So during market hours the column reads a
 * completed day next to a live price, which on a quiet Monday after a heavy
 * Friday is the exact inverse of what the scan is looking for.
 *
 * The live half is a division the quote already carries the numerator for
 * (`volume`, the session's cumulative volume). What it cannot carry is the
 * comparison: volume-so-far over a whole-day average reads a fraction of where
 * the day will end, and two venues at different points in their sessions can't
 * be ranked against each other at all — which is most of what this column is
 * for. `quote.volume_pace` closes that, from the venue's fitted intraday volume
 * curve: the fraction of a normal session traded by now. Dividing by it states
 * the reading in whole-day terms.
 *
 * Not elapsed clock time. Volume is front- and back-loaded by the opening and
 * closing auctions, so a flat assumption reads roughly twice too hot in the
 * first half hour — loudest exactly where a scan is most likely to act on it.
 */

import type { IndicatorSummary, Quote } from "@/lib/types"
import { getNumericValue } from "@/lib/indicator-registry"
import type { LiveResolution } from "@/lib/live-resolution"

/**
 * Below this much of a session traded, the live reading is not published.
 *
 * Not a taste threshold. The pace divides, so its own error is multiplied by
 * 1/pace: at 2% of a session traded, a curve off by a tenth of a percent moves
 * the answer by 5%, and a single block trade prints 10×. The settled value is
 * shown instead, labelled with the session it belongs to, until the denominator
 * is large enough to be worth dividing by.
 */
export const MIN_VOLUME_PACE = 0.02

/** Resolve what the RVOL column should show for one asset. */
export function resolveRvol(
  quote: Quote | undefined,
  snapshot: IndicatorSummary | undefined,
): LiveResolution {
  if (!snapshot) return { status: "withheld", reason: { kind: "no_data" } }

  const stored = getNumericValue(snapshot.values, "rvol")
  const settled: LiveResolution = stored != null
    ? { status: "ok", value: stored, source: "settled" }
    : { status: "withheld", reason: { kind: "no_data" } }

  const pace = quote?.volume_pace
  const volume = quote?.volume
  const baseline = getNumericValue(snapshot.values, "avg_volume")

  // Any of these missing is the ordinary case, not a fault: the venue is
  // closed, has no fitted curve, or the snapshot is too young for a 20-day
  // average. The settled value is still true about the session it names.
  if (pace == null || pace < MIN_VOLUME_PACE || volume == null || baseline == null || baseline <= 0) {
    return settled
  }

  return { status: "ok", value: volume / baseline / pace, source: "live" }
}

/** Human explanation for a blanked RVOL. The live path never blanks — it falls
 * back to the settled value — so the only case left is a snapshot with no
 * `rvol` at all, which says nothing worth a tooltip. */
export function rvolWithheldTitle(): string | null {
  return null
}
