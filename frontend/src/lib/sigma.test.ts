import { describe, it, expect } from "vitest"
import { resolveSigma, sigmaSortKey, VNR_WARMUP_SESSIONS } from "./sigma"
import { VNR_MAX_SESSIONS_BEHIND } from "@/lib/generated/backend-constants"
import type { IndicatorSummary, Quote } from "@/lib/types"

// The Taihan Cable & Solution (001440.KS) case that motivated the original
// cascade: the DB was stuck on Friday's +8.81% up-bar (close 30250, vnr +1.56)
// while the live quote had moved two sessions on (prev 28300, price 28000,
// change -1.06%). σ-Move showed +1.56 next to a red day.

const q = (over: Partial<Quote> = {}): Quote => ({
  symbol: "X", price: null, previous_close: null, change: null, change_percent: null,
  volume: null, avg_volume: null, currency: "USD", market_state: null,
  session_date: null, recent_sessions: null, ...over,
})

const snap = (over: Partial<IndicatorSummary> = {}): IndicatorSummary => ({
  close: null, as_of: null, change_pct: null, bars: 300, values: {}, ...over,
})

/** Six real sessions, newest first — Tue 11th back through Tue 4th of August
 * 2026, skipping the weekend. Index in this list IS the distance a stored bar
 * sits behind the live session. */
const SESSIONS = [
  "2026-08-11", "2026-08-10", "2026-08-07",
  "2026-08-06", "2026-08-05", "2026-08-04",
]

/** A quote dated Tuesday, carrying the venue's recent session window. */
const dated = (over: Partial<Quote> = {}) =>
  q({ session_date: SESSIONS[0], recent_sessions: SESSIONS, ...over })

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

  it("never shows the stored σ once the bar has been superseded", () => {
    // The stored +1.56 describes 08-07. Rendering it beside a live red day is
    // the sign contradiction this module exists to prevent — so even though
    // the bar is close enough to score, the answer comes from the quote.
    const r = resolveSigma(
      dated({ change_percent: -1.06, previous_close: 28300, price: 28000 }),
      snap({ close: 30250, as_of: "2026-08-07", values: { vnr: 1.56, vnr_sigma: 0.0576 } }),
    )
    expect(r).toEqual({ status: "ok", sigma: expect.closeTo(-0.184, 3), source: "live" })
  })

  it("uses the calendar, not arithmetic, for the prior session", () => {
    // Easter Monday: the prior session is the Thursday. "Minus one business
    // day" would name Good Friday and reject a perfectly good stored bar.
    const r = resolveSigma(
      q({ session_date: "2025-04-21", recent_sessions: ["2025-04-21", "2025-04-17", "2025-04-16"],
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
    session_date: "2026-08-13", recent_sessions: ["2026-08-13", "2026-08-12", "2026-08-11"],
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

describe("resolveSigma — a bar several sessions behind (#642)", () => {
  // PRY.MI on 2026-08-19, measured: our last stored bar was 08-17 while the
  // venue had traded 08-18 (a -4.88% day we never stored). The numerator is
  // unaffected — the quote's change % is measured against 08-18's real close —
  // so only the forecast is stale, by one EWMA update.
  const pry = snap({
    close: 131.05, as_of: "2026-08-07",
    values: { vnr: 0.9, vnr_sigma: 0.02449 },
  })

  it("scores from the quote when the bar is two sessions back", () => {
    const r = resolveSigma(dated({ change_percent: -0.4, previous_close: 124.65 }), pry)
    expect(r).toEqual({ status: "ok", sigma: expect.closeTo(-0.163, 3), source: "live" })
  })

  it("still scores at exactly the tolerance", () => {
    const atLimit = SESSIONS[VNR_MAX_SESSIONS_BEHIND]
    const r = resolveSigma(
      dated({ change_percent: -0.4, previous_close: 124.65 }),
      snap({ ...pry, as_of: atLimit }),
    )
    expect(r).toEqual({ status: "ok", sigma: expect.closeTo(-0.163, 3), source: "live" })
  })

  it("withholds one session past it, and says how far behind", () => {
    const pastLimit = SESSIONS[VNR_MAX_SESSIONS_BEHIND + 1]
    const r = resolveSigma(
      dated({ change_percent: -0.4, previous_close: 124.65 }),
      snap({ ...pry, as_of: pastLimit }),
    )
    expect(r).toEqual({
      status: "withheld",
      reason: { kind: "feed_behind", sessions: VNR_MAX_SESSIONS_BEHIND + 1 },
    })
  })

  it("withholds without a distance when the bar predates the whole window", () => {
    const r = resolveSigma(
      dated({ change_percent: -0.4, previous_close: 124.65 }),
      snap({ ...pry, as_of: "2026-05-04" }),
    )
    expect(r).toEqual({ status: "withheld", reason: { kind: "feed_behind", sessions: null } })
  })

  it("reads the distance off the calendar window, not off business days", () => {
    // 2026-08-07 is two sessions back through a weekend; counting weekdays
    // between the dates would say four, and blank a scorable bar.
    const r = resolveSigma(dated({ change_percent: 1.0, previous_close: 100 }), pry)
    expect(r.status).toBe("ok")
  })

  it("cannot score a distant bar with no forecast, and does not fall back to it", () => {
    // The stored 0.9 describes 08-07. There is no honest way to show it.
    const r = resolveSigma(
      dated({ change_percent: -0.4, previous_close: 124.65 }),
      snap({ ...pry, values: { vnr: 0.9 } }),
    )
    expect(r).toEqual({ status: "withheld", reason: { kind: "cannot_score" } })
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
    expect(r).toEqual({ status: "withheld", reason: { kind: "feed_behind", sessions: null } })
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
      q({ session_date: "2026-08-11", recent_sessions: null,
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
