import type { Price } from "@/lib/types"

interface DailyExtreme {
  /** Close-to-close percentage change for the day. */
  pct: number
  /** ISO date of the day the move occurred. */
  date: string
}

interface Drawdown {
  /** Peak-to-trough decline as a (negative) percentage. */
  pct: number
  /** ISO date of the running peak the decline measured from. */
  peakDate: string
  /** ISO date of the trough (the lowest close after that peak). */
  troughDate: string
}

export interface MovementStats {
  /** Total return from the first close in the window to the latest close, as a percentage. */
  periodReturnPct: number
  /** First close in the window (baseline for the period return). */
  startClose: number
  /** Latest close in the window. */
  endClose: number
  /** Largest single-day gain (close-to-close); `pct` is positive. Null when the window has no up day. */
  maxDailyGain: DailyExtreme | null
  /** Largest single-day loss (close-to-close); `pct` is negative. Null when the window has no down day. */
  maxDailyLoss: DailyExtreme | null
  /** Largest peak-to-trough decline over the window. Null when the close never fell below a running peak. */
  maxDrawdown: Drawdown | null
  /** Count of days that closed higher than the previous close. */
  upDays: number
  /** Count of days that closed lower than the previous close. */
  downDays: number
  /** Number of day-over-day transitions considered (prices.length - 1). */
  tradingDays: number
}

/**
 * Derive period movement and downside metrics from an OHLCV series.
 *
 * Pure and side-effect-free — operates only on the passed `prices` (assumed
 * ascending by date, as returned by the asset-detail endpoint). Returns null
 * when there is too little data (< 2 points) or the baseline close is invalid.
 *
 * Note: "max daily move" (single-day, close-to-close) and "max drawdown"
 * (path-dependent peak-to-trough) are distinct metrics; both are reported.
 */
export function computeMovementStats(prices: Price[]): MovementStats | null {
  if (prices.length < 2) return null

  const first = prices[0]
  const last = prices[prices.length - 1]
  if (first.close <= 0) return null

  let maxDailyGain: DailyExtreme | null = null
  let maxDailyLoss: DailyExtreme | null = null
  let upDays = 0
  let downDays = 0

  // Running-peak drawdown: track the highest close seen so far and the largest
  // decline measured from it.
  let peak = first.close
  let peakDate = first.date
  let maxDrawdown: Drawdown | null = null

  for (let i = 1; i < prices.length; i++) {
    const prev = prices[i - 1].close
    const { close: cur, date } = prices[i]

    if (prev > 0) {
      const dayPct = (cur / prev - 1) * 100
      if (dayPct > 0) upDays++
      else if (dayPct < 0) downDays++
      // Sign-guarded so an all-up (or all-down) window can't file the smallest
      // gain under "Max daily loss" (or vice versa): a gain is only a gain, a
      // loss only a loss. A window with no down day leaves maxDailyLoss null,
      // which the UI renders as "—".
      if (dayPct > 0 && (maxDailyGain === null || dayPct > maxDailyGain.pct)) maxDailyGain = { pct: dayPct, date }
      if (dayPct < 0 && (maxDailyLoss === null || dayPct < maxDailyLoss.pct)) maxDailyLoss = { pct: dayPct, date }
    }

    if (cur > peak) {
      peak = cur
      peakDate = date
    } else if (peak > 0) {
      const ddPct = (cur / peak - 1) * 100
      if (maxDrawdown === null || ddPct < maxDrawdown.pct) {
        maxDrawdown = { pct: ddPct, peakDate, troughDate: date }
      }
    }
  }

  return {
    periodReturnPct: (last.close / first.close - 1) * 100,
    startClose: first.close,
    endClose: last.close,
    maxDailyGain,
    maxDailyLoss,
    maxDrawdown,
    upDays,
    downDays,
    tradingDays: prices.length - 1,
  }
}
