import { describe, it, expect } from "vitest"
import { RAMP_COLORS, rampColor, sigmaUnit } from "./color-scale"

const NEUTRAL = RAMP_COLORS[3]

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
})

describe("rampColor — continuous diverging scale", () => {
  it("hits the exact stops at the midpoint and clamped extremes", () => {
    expect(rampColor(0, "sigma").color).toBe(NEUTRAL)
    expect(rampColor(3, "sigma").color).toBe(RAMP_COLORS[6])
    expect(rampColor(-3, "sigma").color).toBe(RAMP_COLORS[0])
    expect(rampColor(99, "sigma").color).toBe(RAMP_COLORS[6]) // clamps
  })

  it("moves linearly — adjacent values differ by a shade, not a cliff", () => {
    // The +0.7σ-grey-next-to-+0.8σ-green complaint: both must sit strictly
    // between neutral and the +1σ stop, and 0.8 must be greener than 0.7.
    const c7 = rampColor(0.7, "sigma").color
    const c8 = rampColor(0.8, "sigma").color
    expect(c7).not.toBe(NEUTRAL)
    expect(c8).not.toBe(NEUTRAL)
    expect(c7).not.toBe(c8)
    const green = (hex: string) => parseInt(hex.slice(3, 5), 16)
    expect(green(c8)).toBeGreaterThan(green(c7))
    expect(green(c8)).toBeLessThan(green(RAMP_COLORS[6]))
  })

  it("scales with the day-adaptive unit", () => {
    // unit 0.5 halves the span: +1.5σ is already the extreme.
    expect(rampColor(1.5, "sigma", undefined, 0.5).color).toBe(RAMP_COLORS[6])
    expect(rampColor(1.5, "sigma", undefined, 1).color).not.toBe(RAMP_COLORS[6])
  })

  it("rescales per window in % mode so a month doesn't render all-extremes", () => {
    expect(rampColor(7, "pct", "1wk").color).toBe(RAMP_COLORS[6])
    expect(rampColor(7, "pct", "1mo").color).not.toBe(RAMP_COLORS[6])
  })

  it("always supplies a legible ink", () => {
    for (const v of [-3, -1.2, 0, 0.4, 2.9]) {
      expect(rampColor(v, "sigma").ink).toMatch(/^#/)
    }
  })
})
