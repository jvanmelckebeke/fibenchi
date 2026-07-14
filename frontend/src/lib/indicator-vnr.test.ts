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
      { change_percent: -1.06, previous_close: 28300 },
      { vnr_sigma: 0.0576 },
      28300,
    )
    // -1.06% / 5.76% ≈ -0.184: negative, agreeing with the red day.
    expect(v).toBeCloseTo(-0.184, 3)
  })

  it("returns null (→ caller falls back) when the stored bar isn't the quote's prior session", () => {
    // Friday close 30250 vs Monday previous_close 28300 → >0.5% apart.
    expect(
      computeLiveVnr({ change_percent: -1.06, previous_close: 28300 }, { vnr_sigma: 0.0576 }, 30250),
    ).toBeNull()
  })

  it("returns null when quote or forecast data is missing/degenerate", () => {
    expect(computeLiveVnr(undefined, { vnr_sigma: 0.0576 }, 28300)).toBeNull()
    expect(computeLiveVnr({ change_percent: -1.06, previous_close: 28300 }, {}, 28300)).toBeNull()
    expect(
      computeLiveVnr({ change_percent: -1.06, previous_close: 28300 }, { vnr_sigma: 0 }, 28300),
    ).toBeNull()
    expect(
      computeLiveVnr({ change_percent: -1.06, previous_close: 28300 }, { vnr_sigma: 0.0576 }, 0),
    ).toBeNull()
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
