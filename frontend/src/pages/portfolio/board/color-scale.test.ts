import { describe, it, expect } from "vitest"
import { RAMP, rampStop, sigmaUnit } from "./color-scale"

describe("sigmaUnit — day-adaptive σ scale", () => {
  it("tightens on quiet days but floors at a ±1.5σ range", () => {
    expect(sigmaUnit([0.2, -0.3, 0.1])).toBe(0.5) // dead calm → floor
    expect(sigmaUnit([2.1, -0.4])).toBeCloseTo(0.7)
  })
  it("caps at the canonical ±3σ on wild days", () => {
    expect(sigmaUnit([4.2, -1.0])).toBe(1)
  })
  it("defaults to the canonical scale with no readings", () => {
    expect(sigmaUnit([])).toBe(1)
  })
  it("spreads a quiet day across the ramp instead of all-neutral", () => {
    // max |σ| = 1.5 → unit 0.5 → edges ±0.5/1/1.5: a +1.4σ day gets strong colour.
    expect(rampStop(1.4, "sigma", undefined, 0.5)).toBe(RAMP[5])
    expect(rampStop(1.4, "sigma", undefined, 1)).toBe(RAMP[4])
  })
})

describe("rampStop — σ mode", () => {
  it("buckets on the fixed ±1/2/3 edges", () => {
    expect(rampStop(-3.5, "sigma")).toBe(RAMP[0])
    expect(rampStop(-2.2, "sigma")).toBe(RAMP[1])
    expect(rampStop(-1.01, "sigma")).toBe(RAMP[2])
    expect(rampStop(0, "sigma")).toBe(RAMP[3]) // neutral grey midpoint
    expect(rampStop(0.99, "sigma")).toBe(RAMP[3])
    expect(rampStop(1.5, "sigma")).toBe(RAMP[4])
    expect(rampStop(2.7, "sigma")).toBe(RAMP[5])
    expect(rampStop(3.0, "sigma")).toBe(RAMP[6])
  })
})

describe("rampStop — % mode", () => {
  it("rescales the edges per window so a month doesn't render all-extremes", () => {
    // +6% is near-extreme over a week (±7 scale)…
    expect(rampStop(6, "pct", "1wk")).toBe(RAMP[5])
    // …but only mildly positive over a month (±14 scale).
    expect(rampStop(6, "pct", "1mo")).toBe(RAMP[4])
    // The neutral band scales too: ±2% over a month is "nothing happened".
    expect(rampStop(2, "pct", "1mo")).toBe(RAMP[3])
    expect(rampStop(-15, "pct", "1mo")).toBe(RAMP[0])
  })
})
