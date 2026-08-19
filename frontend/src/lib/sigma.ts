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
  VNR_WARMUP_SESSIONS,
} from "@/lib/generated/backend-constants"

export { VNR_WARMUP_SESSIONS }

export type SigmaSource = "live" | "settled"

/** Why no σ is shown. Kept discriminated even where the UI collapses them:
 * the distinction decides *whether* to withhold, and the tooltip explains it. */
export type WithheldReason =
  /** The stored bar predates the quote by 2+ sessions. */
  | { kind: "feed_behind" }
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

/** How the snapshot's bar relates to the quote's session. */
type SessionRelation =
  /** The stored bar *is* the quote's session. */
  | "current"
  /** The stored bar is the session immediately before the quote's. */
  | "prior"
  /** Two or more sessions back. */
  | "behind"
  /** No quote at all — σ and the change % beside it share the stored bar. */
  | "none"
  /** Nothing to compare — a provider placeholder with no prices and no dates.
   * Deliberately not "behind": absence of evidence is not evidence of
   * staleness, and reading it as such blanked every symbol at once whenever
   * the provider hiccuped (#632). */
  | "unknown"

function near(a: number | null | undefined, b: number | null | undefined): boolean {
  if (a == null || b == null || b === 0) return false
  return Math.abs(a - b) / Math.abs(b) <= SESSION_MATCH_TOL
}

function relateSession(snapshot: IndicatorSummary, quote: Quote | undefined): SessionRelation {
  if (!quote) return "none"
  const asOf = snapshot.as_of
  const session = quote.session_date

  if (asOf && session) {
    if (asOf === session) return "current"
    if (quote.prior_session_date) {
      // Exact: the calendar already answered "which session came before".
      return asOf === quote.prior_session_date ? "prior" : "behind"
    }
    // Venue has no calendar. We know it isn't the current session; whether it
    // is the one before has to be corroborated on price.
    return near(quote.previous_close, snapshot.close) ? "prior" : "behind"
  }

  // Pre-#626 cached snapshot, or a quote the provider couldn't date.
  if (near(quote.price, snapshot.close)) return "current"
  if (near(quote.previous_close, snapshot.close)) return "prior"
  // Matching neither is real evidence of staleness — but only if there was
  // something to match against. A provider placeholder carries no prices at
  // all, and reading that as "behind" blanked every symbol simultaneously
  // while blaming the user's data for the provider's hiccup (#632).
  if (quote.price == null && quote.previous_close == null) return "unknown"
  return "behind"
}

/**
 * Resolve what the σ column should show for one asset.
 *
 * The order matters and is the whole point of having one function:
 *
 * 1. **Live** when the quote covers a session the stored series doesn't — the
 *    stored bar is the prior session, or it is the current session but
 *    gap-flagged (the stored `vnr` is then null, yet the quote's
 *    `previous_close` *is* the missing session's close, so `change_percent` is
 *    a verified single-session return — #625).
 * 2. **Stored** when the bar is the quote's own session, or there is no quote
 *    to contradict it. Note this is checked *before* any live recompute for a
 *    settled bar: dividing today's return by a forecast that already absorbed
 *    today's move is the mis-denomination #626 describes.
 * 3. **Withheld**, with the most specific reason available.
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

  const relation = relateSession(snapshot, quote)
  const change = quote?.change_percent
  const canScoreLive = change != null && forecast != null && forecast > 0

  if (canScoreLive && (relation === "prior" || (relation === "current" && gap != null))) {
    return { status: "ok", sigma: change / 100 / forecast, source: "live" }
  }

  if (stored != null && (relation === "current" || relation === "none" || relation === "unknown")) {
    return { status: "ok", sigma: stored, source: "settled" }
  }

  if (relation === "behind") return { status: "withheld", reason: { kind: "feed_behind" } }
  if (gap != null) return { status: "withheld", reason: { kind: "gap", sessions: gap } }
  if (bars != null && bars < VNR_WARMUP_SESSIONS) {
    return { status: "withheld", reason: { kind: "warmup", bars, needed: VNR_WARMUP_SESSIONS } }
  }
  if (relation === "prior") return { status: "withheld", reason: { kind: "cannot_score" } }
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
      return "σ-Move unavailable — price data is behind the live quote. A background job reconciles this automatically (usually within ~10 min)."
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
