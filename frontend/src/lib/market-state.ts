// Single source of truth for market-state presentation. Previously the dot
// colour+label map (market-status-dot) and the live-day-view label map lived
// separately and had drifted ("Market open" vs "Regular", "After-hours" vs
// "Post-Market"). Both now consume this.

export interface MarketStateInfo {
  /** Tailwind background class for a status dot. */
  dotColor: string
  /** Human-readable label. */
  label: string
  /**
   * Scheduled-phase equivalent — same vocabulary as the backend venue
   * calendar's phase(). "closed" means prices are settled. PREPRE is Yahoo's
   * overnight state (POST→POSTPOST→PREPRE→PRE): for European venues it lasts
   * the whole night, so it must not masquerade as pre-market. POSTPOST is
   * "after-hours has *ended*" ("POSTMARKET" is not a thing Yahoo emits).
   */
  phase: "premarket" | "open" | "aftermarket" | "closed"
}

const MARKET_STATES = {
  PRE: { dotColor: "bg-blue-500", label: "Pre-market", phase: "premarket" },
  PREPRE: { dotColor: "bg-zinc-500", label: "Overnight", phase: "closed" },
  REGULAR: { dotColor: "bg-emerald-500", label: "Market open", phase: "open" },
  POST: { dotColor: "bg-orange-500", label: "After-hours", phase: "aftermarket" },
  POSTPOST: { dotColor: "bg-red-500", label: "Closed", phase: "closed" },
  CLOSED: { dotColor: "bg-red-500", label: "Closed", phase: "closed" },
} as const satisfies Record<string, MarketStateInfo>

/**
 * The market-state vocabulary the backend emits (Yahoo's, hand-mirrored from
 * `backend/app/schemas/quote.py` — no codegen). Comparing a MarketState
 * against a string outside this union is a compile error, which is the point:
 * a `=== "POSTMARKET"` typo can no longer type-check.
 */
export type MarketState = keyof typeof MARKET_STATES

const DEFAULT_STATE: MarketStateInfo = { dotColor: "bg-red-500", label: "Closed", phase: "closed" }

/** Resolve a market-state code to its dot colour + label (falls back to Closed). */
export function marketState(state: MarketState | null | undefined): MarketStateInfo {
  // Runtime guard stays: the API cast is unchecked, so a novel Yahoo state
  // must still degrade to Closed instead of exploding.
  return (state && MARKET_STATES[state]) || DEFAULT_STATE
}
