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
