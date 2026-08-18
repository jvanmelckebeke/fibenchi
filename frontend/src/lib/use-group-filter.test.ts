import { describe, it, expect } from "vitest"
import { getSortValue } from "./use-group-filter"
import type { Asset, Quote, IndicatorSummary } from "@/lib/api"

// getSortValue must key the σ-Move sort off the SAME value the row renders,
// including blanking a stored σ-Move that predates the live quote (else a
// blanked row would sort by its hidden stale number). Real Taihan numbers.

const asset = { symbol: "001440.KS" } as Asset
const quote = (q: Partial<Quote>): Record<string, Quote> => ({
  "001440.KS": q as Quote,
})
const indicators = (
  close: number | null,
  vnr: number,
  vnr_sigma: number,
  as_of: string | null = null,
): Record<string, IndicatorSummary> => ({
  "001440.KS": { close, as_of, change_pct: null, bars: null, values: { vnr, vnr_sigma } },
})

describe("getSortValue — σ-Move (vnr)", () => {
  it("sorts by the live-recomputed value when the stored bar is the quote's prior session", () => {
    const v = getSortValue(
      asset,
      "vnr",
      quote({ change_percent: -1.06, previous_close: 28300, price: 28100 }),
      indicators(28300, 1.56, 0.0576),
    )
    // Live: -1.06% / 5.76% ≈ -0.184 — NOT the stale stored +1.56.
    expect(v).toBeCloseTo(-0.184, 3)
  })

  it("sorts a stale σ-Move as null (mirrors the blanked cell), not by the stored number", () => {
    const v = getSortValue(
      asset,
      "vnr",
      quote({ change_percent: -1.06, previous_close: 28300, price: 28000 }),
      indicators(30250, 1.56, 0.0576), // Friday's stored bar — 2 sessions behind
    )
    expect(v).toBeNull()
  })

  it("falls back to the stored σ-Move when it is current (bar == quote's session)", () => {
    const v = getSortValue(
      asset,
      "vnr",
      quote({ change_percent: -1.06, previous_close: 28300, price: 28000 }),
      indicators(28000, -0.18, 0.0576), // today's bar synced → dbClose == price
    )
    expect(v).toBe(-0.18)
  })

  it("falls back to the stored σ-Move when there is no live quote", () => {
    const v = getSortValue(asset, "vnr", {}, indicators(30250, 1.56, 0.0576))
    expect(v).toBe(1.56)
  })
})
