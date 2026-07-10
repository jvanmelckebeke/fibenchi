// Single source of truth for market-state presentation. Previously the dot
// colour+label map (market-status-dot) and the live-day-view label map lived
// separately and had drifted ("Market open" vs "Regular", "After-hours" vs
// "Post-Market"). Both now consume this.

export interface MarketStateInfo {
  /** Tailwind background class for a status dot. */
  dotColor: string
  /** Human-readable label. */
  label: string
}

const MARKET_STATES: Record<string, MarketStateInfo> = {
  PRE: { dotColor: "bg-blue-500", label: "Pre-market" },
  PREPRE: { dotColor: "bg-blue-500", label: "Pre-market" },
  REGULAR: { dotColor: "bg-emerald-500", label: "Market open" },
  POST: { dotColor: "bg-orange-500", label: "After-hours" },
  POSTPOST: { dotColor: "bg-orange-500", label: "After-hours" },
  CLOSED: { dotColor: "bg-red-500", label: "Closed" },
}

const DEFAULT_STATE: MarketStateInfo = { dotColor: "bg-red-500", label: "Closed" }

/** Resolve a raw market-state code to its dot colour + label (falls back to Closed). */
export function marketState(state: string | null | undefined): MarketStateInfo {
  return (state && MARKET_STATES[state]) || DEFAULT_STATE
}
