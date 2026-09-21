import { describe, it, expect } from "vitest"
import {
  indicatorSortKey,
  indicatorWithheldTitle,
  isAbnormallyBehind,
  resolveIndicatorValue,
  settledSessionTitle,
} from "./indicator-value"
import type { IndicatorSummary, Quote } from "@/lib/types"

/** Six real sessions, newest first — Tue 11th back through Tue 4th of August
 * 2026, skipping the weekend. Index in this list IS the distance a stored bar
 * sits behind the live session. */
const SESSIONS = [
  "2026-08-11", "2026-08-10", "2026-08-07",
  "2026-08-06", "2026-08-05", "2026-08-04",
]

const q = (over: Partial<Quote> = {}): Quote => ({
  symbol: "X", price: null, previous_close: null, change: null, change_percent: null,
  volume: null, avg_volume: null, currency: "USD", market_state: null,
  session_date: SESSIONS[0], recent_sessions: SESSIONS, ...over,
})

const snap = (over: Partial<IndicatorSummary> = {}): IndicatorSummary => ({
  close: null, as_of: null, change_pct: null, bars: 300, values: {}, ...over,
})

describe("resolveIndicatorValue — settled fields", () => {
  it("reads a plain indicator straight off the snapshot", () => {
    const r = resolveIndicatorValue("rvol", q(), snap({ as_of: SESSIONS[1], values: { rvol: 4.55 } }))
    expect(r).toEqual({ status: "ok", value: 4.55, source: "settled", behind: 1 })
  })

  it("reports the distance even when the number is fine — the whole point", () => {
    // KOG.OL on a Monday with Oslo open: 4.55× is Friday's, and only `behind`
    // says so.
    const r = resolveIndicatorValue("rsi", q(), snap({ as_of: SESSIONS[3], values: { rsi: 61.2 } }))
    expect(r.behind).toBe(3)
  })

  it("withholds a field the snapshot has no value for", () => {
    const r = resolveIndicatorValue("rvol", q(), snap({ as_of: SESSIONS[0], values: {} }))
    expect(r).toEqual({ status: "withheld", reason: { kind: "no_data" }, behind: 0 })
  })

  it("withholds with no distance when there is no snapshot at all", () => {
    expect(resolveIndicatorValue("rvol", q(), undefined)).toEqual({
      status: "withheld", reason: { kind: "no_data" }, behind: null,
    })
  })

  it("leaves the distance unknown when the quote cannot date the bar", () => {
    const r = resolveIndicatorValue("rvol", undefined, snap({ values: { rvol: 1.2 } }))
    expect(r).toEqual({ status: "ok", value: 1.2, source: "settled", behind: null })
  })
})

describe("resolveIndicatorValue — live fields dispatch to their resolver", () => {
  it("scores σ-Move live from the quote when the bar is the prior session", () => {
    const r = resolveIndicatorValue(
      "vnr",
      q({ change_percent: -1.06, previous_close: 28300, price: 28000 }),
      snap({ close: 28300, as_of: SESSIONS[1], values: { vnr: 1.56, vnr_sigma: 0.0576 } }),
    )
    expect(r.status).toBe("ok")
    expect(r).toMatchObject({ source: "live", behind: 1 })
  })

  it("routes σ-Move's own withheld reasons through, not a generic no_data", () => {
    const r = resolveIndicatorValue(
      "vnr",
      q({ change_percent: 2, previous_close: 100, price: 102 }),
      snap({ close: 100, as_of: SESSIONS[5], values: { vnr: 1.1, vnr_sigma: 0.02 } }),
    )
    expect(r).toMatchObject({ status: "withheld", reason: { kind: "feed_behind", sessions: 5 } })
  })

  it("does not treat a live indicator's other fields as live", () => {
    // `vnr_sigma` is an input to the σ resolution, not an output of it.
    const r = resolveIndicatorValue(
      "vnr_sigma",
      q({ change_percent: -1.06 }),
      snap({ as_of: SESSIONS[1], values: { vnr_sigma: 0.0576 } }),
    )
    expect(r).toEqual({ status: "ok", value: 0.0576, source: "settled", behind: 1 })
  })
})

describe("indicatorSortKey", () => {
  it("is the number the row renders, so the sort cannot order by a hidden value", () => {
    const withheld = resolveIndicatorValue("rvol", q(), snap({ as_of: SESSIONS[0] }))
    expect(indicatorSortKey(withheld)).toBeNull()
    expect(indicatorSortKey(resolveIndicatorValue("rvol", q(), snap({ values: { rvol: 2 } })))).toBe(2)
  })
})

describe("isAbnormallyBehind", () => {
  const at = (behind: number) =>
    resolveIndicatorValue("rvol", q(), snap({ as_of: SESSIONS[behind], values: { rvol: 1 } }))

  it("ignores the one-session lag every open session produces", () => {
    expect(isAbnormallyBehind(at(0))).toBe(false)
    expect(isAbnormallyBehind(at(1))).toBe(false)
  })

  it("flags a stored-history hole", () => {
    expect(isAbnormallyBehind(at(2))).toBe(true)
    expect(isAbnormallyBehind(at(4))).toBe(true)
  })

  it("never flags a live-scored value", () => {
    const live = resolveIndicatorValue(
      "vnr",
      q({ change_percent: -1.06, previous_close: 28300, price: 28000 }),
      snap({ close: 28300, as_of: SESSIONS[1], values: { vnr: 1.56, vnr_sigma: 0.0576 } }),
    )
    expect(isAbnormallyBehind(live)).toBe(false)
  })

  it("does not flag an undatable bar as behind", () => {
    expect(isAbnormallyBehind(resolveIndicatorValue("rvol", undefined, snap({ values: { rvol: 1 } })))).toBe(false)
  })
})

describe("settledSessionTitle", () => {
  it("names the session a one-bar-old value describes", () => {
    const r = resolveIndicatorValue("rvol", q(), snap({ as_of: SESSIONS[1], values: { rvol: 4.55 } }))
    expect(settledSessionTitle("RVOL", r, snap({ as_of: SESSIONS[1] }))).toContain(SESSIONS[1])
  })

  it("says nothing about a value that already is the live session", () => {
    const r = resolveIndicatorValue("rvol", q(), snap({ as_of: SESSIONS[0], values: { rvol: 1 } }))
    expect(settledSessionTitle("RVOL", r, snap({ as_of: SESSIONS[0] }))).toBeNull()
  })

  it("says nothing about a live-scored value", () => {
    const live = resolveIndicatorValue(
      "vnr",
      q({ change_percent: -1.06, previous_close: 28300, price: 28000 }),
      snap({ close: 28300, as_of: SESSIONS[1], values: { vnr: 1.56, vnr_sigma: 0.0576 } }),
    )
    expect(settledSessionTitle("σ-Move", live, snap({ as_of: SESSIONS[1] }))).toBeNull()
  })
})

describe("indicatorWithheldTitle", () => {
  it("explains a live resolver's refusal in that resolver's terms", () => {
    const title = indicatorWithheldTitle("vnr", { kind: "gap", sessions: 3 })
    expect(title).toContain("σ-Move")
  })

  it("has nothing to say about a settled field that is simply absent", () => {
    expect(indicatorWithheldTitle("rvol", { kind: "no_data" })).toBeNull()
  })
})
