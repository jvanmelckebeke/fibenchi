/**
 * σ-Move (vnr) resolution — the one place that decides what the σ column shows.
 *
 * σ-Move is a *scanning* primitive: "which of my names did something large
 * relative to how much that name normally moves?" It is read by rank and by
 * colour more than as a number, which sets the cost of each failure. A blank
 * is expensive — it removes a row from the scan and, on the board, shrinks the
 * colour ramp so the calm remainder is repainted louder. A *wrong-signed*
 * number is worse, and is the failure this module exists to prevent: the
 * stored σ describes a completed daily bar, and rendering it next to a live
 * change % from a different session can show green σ on a red day.
 *
 * The old cascade answered "which session is this bar?" by comparing two
 * closes within 0.5%. That is a test of how far the price moved, not of which
 * session it was, and it failed precisely on the days worth looking at. Since
 * #626 the snapshot carries `as_of` and the quote carries `session_date` +
 * `prior_session_date` (venue-calendar exact), so the primary test is date
 * equality. The tolerance survives only as *corroboration* where a date is
 * genuinely unavailable.
 *
 * Every consumer goes through {@link resolveSigma}: previously the group
 * table, the board and the sort key each implemented their own ordering of
 * these decisions and agreed only because gap and staleness rarely co-occur
 * (#629).
 */

import type { IndicatorSummary, Quote } from "@/lib/types"
import { getNumericValue } from "@/lib/indicator-registry"

// Both constants are generated from their Python definitions rather than
// restated here — the backend acts on this module's behalf (its heal loop
// predicts what this file will refuse to score), so a silent drift shows up as
// σ blank on symbols the heal reports as repaired, which points at neither
// file. CI regenerates and fails on any difference.
import {
  SESSION_MATCH_TOL,
  VNR_MAX_SESSIONS_BEHIND,
  VNR_WARMUP_SESSIONS,
} from "@/lib/generated/backend-constants"

export { VNR_WARMUP_SESSIONS }

export type SigmaSource = "live" | "settled"

/** Why no σ is shown. Kept discriminated even where the UI collapses them:
 * the distinction decides *whether* to withhold, and the tooltip explains it. */
export type WithheldReason =
  /** The stored bar is further behind the live session than the vol forecast
   * can bridge. `sessions` is the measured distance, or null when the venue
   * has no calendar and all we know is "further back than the prior one". */
  | { kind: "feed_behind"; sessions: number | null }
  /** The stored series is missing sessions, so its own return spans a hole. */
  | { kind: "gap"; sessions: number }
  /** Too little history for the vol baseline to mean anything. */
  | { kind: "warmup"; bars: number; needed: number }
  /** The bar is identified, but there is no usable vol forecast to divide by.
   * Distinct from the others because showing the stored σ here is exactly the
   * sign-contradiction bug — it must blank, not fall back. */
  | { kind: "cannot_score" }
  /** No snapshot, or nothing to say about it. */
  | { kind: "no_data" }

export type SigmaResolution =
  | { status: "ok"; sigma: number; source: SigmaSource }
  | { status: "withheld"; reason: WithheldReason }

/** The stored bar is further back than any window we ship or could score. */
const BEYOND_WINDOW = Number.POSITIVE_INFINITY

function near(a: number | null | undefined, b: number | null | undefined): boolean {
  if (a == null || b == null || b === 0) return false
  return Math.abs(a - b) / Math.abs(b) <= SESSION_MATCH_TOL
}

/**
 * How many venue sessions the stored bar sits behind the quote's live session.
 *
 * 0 means the bar *is* the live session, 1 the session before it, and so on.
 * A distance rather than a category, because that is what the decision below
 * actually needs: the old five-value enum could say "yesterday" or "older",
 * and everything past yesterday collapsed into one bucket that had to be
 * refused wholesale (#642).
 *
 * `null` is *unknowable*, not far: no quote at all, or a provider placeholder
 * carrying neither dates nor prices. Absence of evidence is not evidence of
 * staleness — reading it as such blanked every symbol at once whenever the
 * provider hiccuped (#632).
 */
function sessionsBehind(snapshot: IndicatorSummary, quote: Quote | undefined): number | null {
  if (!quote) return null
  const asOf = snapshot.as_of
  const session = quote.session_date

  if (asOf && session) {
    if (asOf === session) return 0
    // The calendar already counted the sessions, in order — read the distance
    // off the index. Counting business days here instead is the heuristic that
    // turns every holiday into a hole (#559, #633).
    if (quote.recent_sessions?.length) {
      const i = quote.recent_sessions.indexOf(asOf)
      return i >= 0 ? i : BEYOND_WINDOW
    }
    // Venue has no calendar. We know it isn't the live session; whether it is
    // the one before can only be corroborated on price, and nothing further
    // back is distinguishable from anything else.
    return near(quote.previous_close, snapshot.close) ? 1 : BEYOND_WINDOW
  }

  // Pre-#626 cached snapshot, or a quote the provider couldn't date.
  if (near(quote.price, snapshot.close)) return 0
  if (near(quote.previous_close, snapshot.close)) return 1
  if (quote.price == null && quote.previous_close == null) return null
  return BEYOND_WINDOW
}

/** Which number we are entitled to show. */
type Plan = "live" | "settled" | "too-behind"

/**
 * Choose the strategy from the bar's distance alone.
 *
 * Short because the distance already says everything. `vnr_sigma` at bar t is
 * the forecast for session t+1, so:
 *
 * - **d = 0** — the stored `vnr` already scores this session, and its forecast
 *   is for *tomorrow*; dividing today's move by it is the mis-denomination
 *   #626 describes. Show the stored value. The exception is a gap-flagged bar,
 *   whose `vnr` is null while the quote's own single-session return stays
 *   perfectly sound (#625).
 * - **d >= 1** — the stored `vnr` describes a session that has since been
 *   superseded, so it must not be shown next to a live price. But the quote's
 *   `change_percent` is measured against the true previous close, making it a
 *   verified single-session return at *any* distance; only the forecast ages,
 *   by exactly d-1 EWMA updates. Score live while that is within tolerance.
 * - **null** — nothing to contradict the snapshot, so it stands.
 */
function planFor(behind: number | null, gapFlagged: boolean): Plan {
  if (behind === null) return "settled"
  if (behind === 0) return gapFlagged ? "live" : "settled"
  return behind <= VNR_MAX_SESSIONS_BEHIND ? "live" : "too-behind"
}

/**
 * Resolve what the σ column should show for one asset.
 *
 * Three steps, deliberately separate: locate the bar, choose what that entitles
 * us to compute, then either compute it or explain the absence. Every consumer
 * goes through here — the group table, the board, the sort key and the detail
 * page each used to order these decisions their own way and agreed only
 * because gap and staleness rarely co-occur (#629).
 */
export function resolveSigma(
  quote: Quote | undefined,
  snapshot: IndicatorSummary | undefined,
): SigmaResolution {
  if (!snapshot) return { status: "withheld", reason: { kind: "no_data" } }

  const values = snapshot.values
  const forecast = getNumericValue(values, "vnr_sigma")
  const stored = getNumericValue(values, "vnr")
  const gap = getNumericValue(values, "vnr_gap_sessions")
  const bars = snapshot.bars

  const behind = sessionsBehind(snapshot, quote)
  const plan = planFor(behind, gap != null)
  const change = quote?.change_percent
  /** The distance, when it is a real count rather than "off the end". */
  const distance = behind != null && Number.isFinite(behind) ? behind : null

  if (plan === "live" && change != null && forecast != null && forecast > 0) {
    return { status: "ok", sigma: change / 100 / forecast, source: "live" }
  }
  if (plan === "settled" && stored != null) {
    return { status: "ok", sigma: stored, source: "settled" }
  }

  // Nothing renderable. Explain it, most specific cause first.
  if (plan === "too-behind") {
    return { status: "withheld", reason: { kind: "feed_behind", sessions: distance } }
  }
  if (gap != null) return { status: "withheld", reason: { kind: "gap", sessions: gap } }
  if (bars != null && bars < VNR_WARMUP_SESSIONS) {
    return { status: "withheld", reason: { kind: "warmup", bars, needed: VNR_WARMUP_SESSIONS } }
  }
  if (plan === "live") return { status: "withheld", reason: { kind: "cannot_score" } }
  return { status: "withheld", reason: { kind: "no_data" } }
}

/** Sort key: the resolved σ, or null so unresolvable rows sort last. Keeps the
 * ordering identical to what the row renders. */
export function sigmaSortKey(resolution: SigmaResolution): number | null {
  return resolution.status === "ok" ? resolution.sigma : null
}

/** Human explanation for a withheld σ, or null when there is nothing useful to
 * say (the cell is then a mute dash rather than a lying tooltip). */
export function sigmaWithheldTitle(reason: WithheldReason): string | null {
  switch (reason.kind) {
    case "feed_behind":
      return reason.sessions != null
        ? `σ-Move unavailable — stored prices are ${reason.sessions} trading sessions behind the live quote, too far for the volatility baseline to still describe today. A background job backfills this automatically.`
        : "σ-Move unavailable — price data is behind the live quote. A background job reconciles this automatically (usually within ~10 min)."
    case "gap":
      return `σ-Move unavailable — the last return spans ${reason.sessions} trading sessions (gap in stored price history). A background job backfills missing sessions automatically; see the Stats page.`
    case "warmup":
      return `σ-Move unavailable — building the volatility baseline (${reason.bars} of ${reason.needed} sessions).`
    case "cannot_score":
      return "σ-Move unavailable — no volatility baseline to score today's move against."
    case "no_data":
      return null
  }
}
