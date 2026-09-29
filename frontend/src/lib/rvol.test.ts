import { describe, it, expect } from "vitest"
import { resolveRvol, MIN_VOLUME_PACE } from "./rvol"
import type { IndicatorSummary, Quote } from "@/lib/types"

const q = (over: Partial<Quote> = {}): Quote => ({
  symbol: "KOG.OL", price: null, previous_close: null, change: null, change_percent: null,
  volume: null, avg_volume: null, currency: "NOK", market_state: null,
  session_date: null, recent_sessions: null, volume_pace: null, ...over,
})

const snap = (values: Record<string, number | string | null> = {}): IndicatorSummary => ({
  close: null, as_of: "2026-09-18", change_pct: null, bars: 300, values,
})

// KOG.OL: 4.85M on Friday against a 1.27M 20-day average — a true 3.8x that
// says nothing about Monday.
const FRIDAY = { rvol: 3.82, avg_volume: 1269367 }

describe("resolveRvol", () => {
  it("states a part-session's volume in whole-day terms", () => {
    // 700k traded with 30% of a normal session done: pacing for ~2.3M, or 1.8x.
    const r = resolveRvol(q({ volume: 700_000, volume_pace: 0.3 }), snap(FRIDAY))
    expect(r).toEqual({ status: "ok", value: expect.closeTo(1.838, 3), source: "live" })
  })

  it("ranks two venues at different points in their sessions on one scale", () => {
    // Same pace-adjusted heaviness, wildly different raw volume-so-far.
    const early = resolveRvol(q({ volume: 254_000, volume_pace: 0.1 }), snap(FRIDAY))
    const late = resolveRvol(q({ volume: 2_285_000, volume_pace: 0.9 }), snap(FRIDAY))
    expect(early.status === "ok" && early.value).toBeCloseTo(2.0, 1)
    expect(late.status === "ok" && late.value).toBeCloseTo(2.0, 1)
  })

  it("falls back to the settled reading when the venue is closed", () => {
    const r = resolveRvol(q({ volume: 4_846_513, volume_pace: null }), snap(FRIDAY))
    expect(r).toEqual({ status: "ok", value: 3.82, source: "settled" })
  })

  it("falls back before enough of the session has traded to divide by", () => {
    const r = resolveRvol(
      q({ volume: 30_000, volume_pace: MIN_VOLUME_PACE / 2 }),
      snap(FRIDAY),
    )
    expect(r).toMatchObject({ source: "settled" })
  })

  it("scores at the threshold itself, not one tick past it", () => {
    const r = resolveRvol(q({ volume: 30_000, volume_pace: MIN_VOLUME_PACE }), snap(FRIDAY))
    expect(r).toMatchObject({ source: "live" })
  })

  it("falls back when the snapshot has no 20-day average to compare against", () => {
    const r = resolveRvol(q({ volume: 700_000, volume_pace: 0.3 }), snap({ rvol: 3.82 }))
    expect(r).toEqual({ status: "ok", value: 3.82, source: "settled" })
  })

  it("uses the snapshot's 20-day baseline, not the quote's 10-day one", () => {
    // Yahoo's averageDailyVolume10Day rides along on the quote and is a
    // different number; scoring against it would make the live and settled
    // readings incomparable across the session boundary.
    const r = resolveRvol(
      q({ volume: 700_000, volume_pace: 0.3, avg_volume: 500_000 }),
      snap(FRIDAY),
    )
    expect(r).toMatchObject({ value: expect.closeTo(1.838, 3) })
  })

  it("withholds when there is no snapshot at all", () => {
    expect(resolveRvol(q({ volume: 1, volume_pace: 0.5 }), undefined)).toEqual({
      status: "withheld", reason: { kind: "no_data" },
    })
  })

  it("withholds when the snapshot carries neither a stored value nor a baseline", () => {
    expect(resolveRvol(q(), snap({}))).toEqual({
      status: "withheld", reason: { kind: "no_data" },
    })
  })

  it("does not divide by a zero baseline", () => {
    const r = resolveRvol(q({ volume: 700_000, volume_pace: 0.3 }), snap({ rvol: 1, avg_volume: 0 }))
    expect(r).toEqual({ status: "ok", value: 1, source: "settled" })
  })
})
