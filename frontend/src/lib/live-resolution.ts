/**
 * The shape every live-scored indicator answers in.
 *
 * Shared so `lib/indicator-value.ts` can dispatch across resolvers without
 * knowing which one it called, and so the reasons a value is withheld stay one
 * vocabulary — two resolvers inventing their own would leave the table
 * explaining the same absence two ways.
 */

/** Whether a rendered value was recomputed against the live session or read
 * straight off the settled snapshot. */
export type ValueSource = "live" | "settled"

/** Why no value is shown. Kept discriminated even where the UI collapses them:
 * the distinction decides *whether* to withhold, and the tooltip explains it. */
export type WithheldReason =
  /** The stored bar is further behind the live session than the forecast can
   * bridge. `sessions` is the measured distance, or null when the venue has no
   * calendar and all we know is "further back than the prior one". */
  | { kind: "feed_behind"; sessions: number | null }
  /** The stored series is missing sessions, so its own return spans a hole. */
  | { kind: "gap"; sessions: number }
  /** Too little history for the baseline to mean anything. */
  | { kind: "warmup"; bars: number; needed: number }
  /** The bar is identified, but there is no usable baseline to divide by.
   * Distinct from the others because showing the stored value here is exactly
   * the contradiction to avoid — it must blank, not fall back. */
  | { kind: "cannot_score" }
  /** No snapshot, or nothing to say about it. */
  | { kind: "no_data" }

export type LiveResolution =
  | { status: "ok"; value: number; source: ValueSource }
  | { status: "withheld"; reason: WithheldReason }
