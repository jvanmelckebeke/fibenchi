import { describe, it, expect } from "vitest"
import { computeMovementStats } from "./movement-stats"
import type { Price } from "@/lib/types"

/** Build an ascending-by-date price series from a list of closes. */
function series(closes: number[]): Price[] {
  return closes.map((close, i) => ({
    date: `2025-01-${String(i + 1).padStart(2, "0")}`,
    open: close,
    high: close,
    low: close,
    close,
    volume: 1_000_000,
  }))
}

describe("computeMovementStats — max daily gain/loss sign guards", () => {
  it("reports no daily loss for an all-up window (the bug: smallest gain mislabelled as a loss)", () => {
    const stats = computeMovementStats(series([100, 101, 103, 106]))!
    expect(stats.maxDailyLoss).toBeNull()
    expect(stats.maxDailyGain).not.toBeNull()
    expect(stats.maxDailyGain!.pct).toBeGreaterThan(0)
    expect(stats.downDays).toBe(0)
  })

  it("reports no daily gain for an all-down window", () => {
    const stats = computeMovementStats(series([106, 103, 101, 100]))!
    expect(stats.maxDailyGain).toBeNull()
    expect(stats.maxDailyLoss).not.toBeNull()
    expect(stats.maxDailyLoss!.pct).toBeLessThan(0)
    expect(stats.upDays).toBe(0)
  })

  it("picks the correct extreme of each sign in a mixed window", () => {
    // Day moves: +5%, -10% (biggest loss), +1%, +8% (biggest gain).
    const stats = computeMovementStats(series([100, 105, 94.5, 95.445, 103.08]))!
    expect(stats.maxDailyGain!.pct).toBeGreaterThan(stats.maxDailyLoss!.pct)
    expect(stats.maxDailyGain!.pct).toBeGreaterThan(0)
    expect(stats.maxDailyLoss!.pct).toBeLessThan(0)
    // The biggest gain is the last day (~+8%), the biggest loss the second (~-10%).
    expect(stats.maxDailyGain!.date).toBe("2025-01-05")
    expect(stats.maxDailyLoss!.date).toBe("2025-01-03")
  })

  it("treats a flat day as neither a gain nor a loss", () => {
    const stats = computeMovementStats(series([100, 100, 100]))!
    expect(stats.maxDailyGain).toBeNull()
    expect(stats.maxDailyLoss).toBeNull()
    expect(stats.upDays).toBe(0)
    expect(stats.downDays).toBe(0)
  })
})

describe("computeMovementStats — gap awareness (issue #559)", () => {
  it("excludes a multi-session step from daily extremes and counts", () => {
    // Fri 2026-07-31 -> Tue 2026-08-04 with Mon 2026-08-03 missing: the +2.75%
    // step spans two sessions and must not be filed as the max daily gain.
    const prices: Price[] = [
      { date: "2026-07-29", open: 0, high: 0, low: 0, close: 124.33, volume: 1 },
      { date: "2026-07-30", open: 0, high: 0, low: 0, close: 123.69, volume: 1 },
      { date: "2026-07-31", open: 0, high: 0, low: 0, close: 124.23, volume: 1 },
      { date: "2026-08-04", open: 0, high: 0, low: 0, close: 127.65, volume: 1 },
    ]
    const stats = computeMovementStats(prices)!
    // The only single-session up-move is Jul 30 -> Jul 31 (+0.44%).
    expect(stats.maxDailyGain!.date).toBe("2026-07-31")
    expect(stats.maxDailyGain!.pct).toBeCloseTo(0.437, 2)
    expect(stats.upDays).toBe(1)
    expect(stats.downDays).toBe(1)
    expect(stats.tradingDays).toBe(2)
    // Path metrics still use the full window, gap included.
    expect(stats.periodReturnPct).toBeCloseTo((127.65 / 124.33 - 1) * 100, 4)
  })

  it("treats a weekend step as a single session", () => {
    const prices: Price[] = [
      { date: "2026-07-31", open: 0, high: 0, low: 0, close: 100, volume: 1 }, // Fri
      { date: "2026-08-03", open: 0, high: 0, low: 0, close: 105, volume: 1 }, // Mon
    ]
    const stats = computeMovementStats(prices)!
    expect(stats.maxDailyGain!.pct).toBeCloseTo(5, 5)
    expect(stats.tradingDays).toBe(1)
  })
})
