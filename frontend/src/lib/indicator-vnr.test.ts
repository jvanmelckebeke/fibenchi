import { describe, it, expect } from "vitest"
import { computeLiveVnr, isStoredVnrStale } from "./indicator-registry"

// Numbers are the real Taihan Cable & Solution (001440.KS) case that motivated
// the fix: the DB was stuck on Friday's +8.81% up-bar (close 30250, vnr +1.56)
// while the live quote had already moved two sessions on (prev_close 28300,
// price 28000, change -1.06%). σ-Move showed +1.56 next to a red day.

describe("computeLiveVnr", () => {
  it("scores the live move when the stored bar is the quote's prior session", () => {
    // dbClose == previous_close → forecast (vnr_sigma) applies to the live day.
    const v = computeLiveVnr(
      { change_percent: -1.06, previous_close: 28300, price: 28000 },
      { vnr_sigma: 0.0576 },
      28300,
    )
    // -1.06% / 5.76% ≈ -0.184: negative, agreeing with the red day.
    expect(v).toBeCloseTo(-0.184, 3)
  })

  it("returns null (→ caller falls back) when the stored bar isn't the quote's prior session", () => {
    // Friday close 30250 vs Monday previous_close 28300 → >0.5% apart.
    expect(
      computeLiveVnr(
        { change_percent: -1.06, previous_close: 28300, price: 28000 },
        { vnr_sigma: 0.0576 },
        30250,
      ),
    ).toBeNull()
  })

  it("returns null when quote or forecast data is missing/degenerate", () => {
    const q = { change_percent: -1.06, previous_close: 28300, price: 28000 }
    expect(computeLiveVnr(undefined, { vnr_sigma: 0.0576 }, 28300)).toBeNull()
    expect(computeLiveVnr(q, {}, 28300)).toBeNull()
    expect(computeLiveVnr(q, { vnr_sigma: 0 }, 28300)).toBeNull()
    expect(computeLiveVnr(q, { vnr_sigma: 0.0576 }, 0)).toBeNull()
  })
})

// Real XAIX.DE state on 2026-08-13: Yahoo's daily history had no 2026-08-12 bar
// (its own feed jumps 08-11 → 08-13), so the gap guard NaN'd the stored `vnr`.
// The quote still knew the missing session — previous_close 207.45 IS the 08-12
// close — making change_percent a verified single-session return. σ = +0.71.
describe("computeLiveVnr with a gap-flagged snapshot (#625)", () => {
  const gapQuote = { change_percent: 1.18, previous_close: 207.45, price: 209.9 }
  const gapValues = { vnr_sigma: 0.016578, vnr_gap_sessions: 2 }

  it("scores a mover instead of blanking it — the regression", () => {
    // dbClose is the quote's own session, so the prior-session anchor check
    // would reduce to |move| <= 0.5% and reject this +1.18% day.
    expect(computeLiveVnr(gapQuote, gapValues, 209.9)).toBeCloseTo(0.712, 3)
  })

  it("scores movers of either direction at any magnitude", () => {
    const down = { change_percent: -3.35, previous_close: 60.56, price: 58.53 }
    expect(
      computeLiveVnr(down, { vnr_sigma: 0.02638, vnr_gap_sessions: 2 }, 58.53),
    ).toBeCloseTo(-1.27, 2)
  })

  it("still blanks when the stored bar predates the quote entirely", () => {
    // Gap-flagged AND genuinely behind: dbClose matches neither the price nor
    // the previous close, so the forecast is too old to apply. Blank is right.
    expect(computeLiveVnr(gapQuote, gapValues, 180)).toBeNull()
  })

  it("returns null without a quote to recover the missing session from", () => {
    expect(computeLiveVnr(undefined, gapValues, 209.9)).toBeNull()
  })

  it("returns null when the forecast is missing or degenerate", () => {
    expect(computeLiveVnr(gapQuote, { vnr_gap_sessions: 2 }, 209.9)).toBeNull()
    expect(
      computeLiveVnr(gapQuote, { vnr_sigma: 0, vnr_gap_sessions: 2 }, 209.9),
    ).toBeNull()
  })

  it("leaves non-gap-flagged behaviour unchanged", () => {
    // Same numbers without the gap flag: the anchor check applies as before and
    // rejects, because dbClose is the quote's current session.
    expect(computeLiveVnr(gapQuote, { vnr_sigma: 0.016578 }, 209.9)).toBeNull()
  })
})

describe("isStoredVnrStale", () => {
  it("is true when the stored bar predates the live quote by ≥2 sessions (the bug)", () => {
    // Friday's stored close (30250) matches neither the quote's price (28000)
    // nor its previous_close (28300) → stale, so the display/sort must blank it.
    expect(isStoredVnrStale({ price: 28000, previous_close: 28300 }, 30250)).toBe(true)
  })

  it("is false when the stored bar is the quote's current session (today already synced)", () => {
    // Market closed, today's bar stored → dbClose ≈ quote.price → σ-Move is current.
    expect(isStoredVnrStale({ price: 28000, previous_close: 28300 }, 28000)).toBe(false)
  })

  it("is false when the stored bar is the quote's prior session", () => {
    // dbClose ≈ previous_close (computeLiveVnr would produce a live value here).
    expect(isStoredVnrStale({ price: 28100, previous_close: 28300 }, 28300)).toBe(false)
  })

  it("is false without a live quote — σ-Move and change % share the stored bar then", () => {
    expect(isStoredVnrStale(undefined, 30250)).toBe(false)
  })

  it("is false when there is no stored close to anchor against", () => {
    expect(isStoredVnrStale({ price: 28000, previous_close: 28300 }, null)).toBe(false)
    expect(isStoredVnrStale({ price: 28000, previous_close: 28300 }, 0)).toBe(false)
  })
})
