import { describe, it, expect } from "vitest"
import { resolveSigma, sigmaSortKey, VNR_WARMUP_SESSIONS } from "./sigma"
import type { IndicatorSummary, Quote } from "@/lib/types"

// The Taihan Cable & Solution (001440.KS) case that motivated the original
// cascade: the DB was stuck on Friday's +8.81% up-bar (close 30250, vnr +1.56)
// while the live quote had moved two sessions on (prev 28300, price 28000,
// change -1.06%). σ-Move showed +1.56 next to a red day.

const q = (over: Partial<Quote> = {}): Quote => ({
  symbol: "X", price: null, previous_close: null, change: null, change_percent: null,
  volume: null, avg_volume: null, currency: "USD", market_state: null,
  session_date: null, prior_session_date: null, ...over,
})

const snap = (over: Partial<IndicatorSummary> = {}): IndicatorSummary => ({
  close: null, as_of: null, change_pct: null, bars: 300, values: {}, ...over,
})

/** A quote dated Tuesday whose prior session the calendar says is Monday. */
const dated = (over: Partial<Quote> = {}) =>
  q({ session_date: "2026-08-11", prior_session_date: "2026-08-10", ...over })

describe("resolveSigma — session identity decides, not price similarity", () => {
  it("recomputes live when the stored bar is the quote's prior session", () => {
    const r = resolveSigma(
      dated({ change_percent: -1.06, previous_close: 28300, price: 28000 }),
      snap({ close: 28300, as_of: "2026-08-10", values: { vnr: 1.56, vnr_sigma: 0.0576 } }),
    )
    expect(r).toEqual({ status: "ok", sigma: expect.closeTo(-0.184, 3), source: "live" })
  })

  it("scores a >0.5% mover the old tolerance would have rejected", () => {
    // Identical to the case above but a 12% day: the price-similarity test
    // rejected exactly these, i.e. every symbol worth looking at (#626).
    const r = resolveSigma(
      dated({ change_percent: 12.0, previous_close: 100, price: 112 }),
      snap({ close: 100, as_of: "2026-08-10", values: { vnr: 0.2, vnr_sigma: 0.02 } }),
    )
    expect(r).toEqual({ status: "ok", sigma: expect.closeTo(6, 6), source: "live" })
  })

  it("shows the stored value when the bar IS the quote's session", () => {
    // And does NOT recompute live: the forecast at a settled bar has already
    // absorbed that bar's own move, so dividing by it understates (#626).
    const r = resolveSigma(
      dated({ change_percent: 0.3, previous_close: 100, price: 100.3 }),
      snap({ close: 100.3, as_of: "2026-08-11", values: { vnr: 0.305, vnr_sigma: 0.01 } }),
    )
    expect(r).toEqual({ status: "ok", sigma: 0.305, source: "settled" })
  })

  it("withholds when the stored bar is two or more sessions back", () => {
    const r = resolveSigma(
      dated({ change_percent: -1.06, previous_close: 28300, price: 28000 }),
      snap({ close: 30250, as_of: "2026-08-07", values: { vnr: 1.56, vnr_sigma: 0.0576 } }),
    )
    expect(r).toEqual({ status: "withheld", reason: { kind: "feed_behind" } })
  })

  it("uses the calendar, not arithmetic, for the prior session", () => {
    // Easter Monday: the prior session is the Thursday. "Minus one business
    // day" would name Good Friday and reject a perfectly good stored bar.
    const r = resolveSigma(
      q({ session_date: "2025-04-21", prior_session_date: "2025-04-17",
          change_percent: 2.0, previous_close: 100, price: 102 }),
      snap({ close: 100, as_of: "2025-04-17", values: { vnr: 0.1, vnr_sigma: 0.02 } }),
    )
    expect(r).toEqual({ status: "ok", sigma: expect.closeTo(1, 6), source: "live" })
  })
})

describe("resolveSigma — gap-flagged snapshots (#625)", () => {
  // Real XAIX.DE state: Yahoo's history had no 2026-08-12 bar, so the gap
  // guard NaN'd the stored vnr. The quote still knew the missing session —
  // previous_close 207.45 IS that close — so change_percent is a verified
  // single-session return.
  const gapSnap = snap({
    close: 209.9, as_of: "2026-08-13",
    values: { vnr: null, vnr_sigma: 0.016578, vnr_gap_sessions: 2 },
  })
  const gapQuote = q({
    session_date: "2026-08-13", prior_session_date: "2026-08-12",
    change_percent: 1.18, previous_close: 207.45, price: 209.9,
  })

  it("recovers the reading from the quote instead of blanking a mover", () => {
    expect(resolveSigma(gapQuote, gapSnap)).toEqual(
      { status: "ok", sigma: expect.closeTo(0.712, 3), source: "live" },
    )
  })

  it("explains the blank when there is no quote to recover from", () => {
    expect(resolveSigma(undefined, gapSnap)).toEqual(
      { status: "withheld", reason: { kind: "gap", sessions: 2 } },
    )
  })

  it("explains the blank when the forecast is unusable", () => {
    const noForecast = snap({ ...gapSnap, values: { vnr_gap_sessions: 2, vnr_sigma: 0 } })
    expect(resolveSigma(gapQuote, noForecast)).toEqual(
      { status: "withheld", reason: { kind: "gap", sessions: 2 } },
    )
  })
})

describe("resolveSigma — degraded inputs", () => {
  it("keeps the stored value when a provider placeholder carries no prices", () => {
    // Reading "matches neither" as staleness blanked the whole portfolio at
    // once, blaming the user's data for the provider's hiccup (#632).
    const r = resolveSigma(q(), snap({ close: 100, values: { vnr: 1.2, vnr_sigma: 0.01 } }))
    expect(r).toEqual({ status: "ok", sigma: 1.2, source: "settled" })
  })

  it("still treats a real quote matching neither price as behind", () => {
    const r = resolveSigma(
      q({ price: 28000, previous_close: 28300 }),
      snap({ close: 30250, values: { vnr: 1.56, vnr_sigma: 0.0576 } }),
    )
    expect(r).toEqual({ status: "withheld", reason: { kind: "feed_behind" } })
  })

  it("shows the stored value when there is no quote at all", () => {
    // σ and the change % beside it then come from the same bar and cannot
    // disagree, so there is nothing to protect against.
    const r = resolveSigma(undefined, snap({ close: 100, values: { vnr: 0.9, vnr_sigma: 0.01 } }))
    expect(r).toEqual({ status: "ok", sigma: 0.9, source: "settled" })
  })

  it("falls back to price corroboration for a pre-#626 snapshot", () => {
    const r = resolveSigma(
      q({ change_percent: -1.06, previous_close: 28300, price: 28000 }),
      snap({ close: 28300, values: { vnr: 1.56, vnr_sigma: 0.0576 } }),
    )
    expect(r).toEqual({ status: "ok", sigma: expect.closeTo(-0.184, 3), source: "live" })
  })

  it("corroborates on price when the venue has no calendar", () => {
    const r = resolveSigma(
      q({ session_date: "2026-08-11", prior_session_date: null,
          change_percent: -1.06, previous_close: 28300, price: 28000 }),
      snap({ close: 28300, as_of: "2026-08-10", values: { vnr: 1.56, vnr_sigma: 0.0576 } }),
    )
    expect(r).toEqual({ status: "ok", sigma: expect.closeTo(-0.184, 3), source: "live" })
  })

  it("withholds rather than showing a stored σ with no usable forecast", () => {
    // The prior-session bar is yesterday's; rendering it beside today's live
    // change % is the sign contradiction this whole module exists to prevent.
    const r = resolveSigma(
      dated({ change_percent: -1.06, previous_close: 28300, price: 28000 }),
      snap({ close: 28300, as_of: "2026-08-10", values: { vnr: 1.56 } }),
    )
    expect(r).toEqual({ status: "withheld", reason: { kind: "cannot_score" } })
  })

  it("reports warmup for a series too short to have a baseline", () => {
    const r = resolveSigma(dated(), snap({ close: 100, as_of: "2026-08-11", bars: 12 }))
    expect(r).toEqual({
      status: "withheld",
      reason: { kind: "warmup", bars: 12, needed: VNR_WARMUP_SESSIONS },
    })
  })

  it("reports no_data without a snapshot", () => {
    expect(resolveSigma(dated(), undefined)).toEqual(
      { status: "withheld", reason: { kind: "no_data" } },
    )
  })
})

describe("sigmaSortKey", () => {
  it("is the resolved value, so the sort matches what the row renders", () => {
    const ok = resolveSigma(undefined, snap({ close: 100, values: { vnr: 0.9 } }))
    expect(sigmaSortKey(ok)).toBe(0.9)
  })

  it("is null for a withheld reading, so blanked rows never sort by a hidden number", () => {
    const withheld = resolveSigma(
      dated({ price: 1, previous_close: 2 }),
      snap({ close: 30250, as_of: "2026-08-01", values: { vnr: 1.56 } }),
    )
    expect(sigmaSortKey(withheld)).toBeNull()
  })
})
