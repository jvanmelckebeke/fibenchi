import { describe, it, expect } from "vitest"
import { RAMP_COLORS, pctSpan, rampColor, sigmaUnit } from "./color-scale"

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

describe("pctSpan — day-adaptive %-of-today scale", () => {
  it("tracks the day's biggest move within the ±2 … ±7 band", () => {
    expect(pctSpan([0.3, -0.8])).toBe(2) // flat day → floor
    expect(pctSpan([4.1, -1.2])).toBeCloseTo(4.1)
    expect(pctSpan([12, -3])).toBe(7) // cap
    expect(pctSpan([])).toBe(7)
  })
})

describe("rampColor — continuous diverging scale", () => {
  it("hits the exact stops at the midpoint and clamped extremes", () => {
    expect(rampColor(0, 3).color).toBe(NEUTRAL)
    expect(rampColor(3, 3).color).toBe(RAMP_COLORS[6])
    expect(rampColor(-3, 3).color).toBe(RAMP_COLORS[0])
    expect(rampColor(99, 3).color).toBe(RAMP_COLORS[6]) // clamps
  })

  it("moves linearly — adjacent values differ by a shade, not a cliff", () => {
    // The +0.7σ-grey-next-to-+0.8σ-green complaint: both must sit strictly
    // between neutral and the extreme, and 0.8 must be greener than 0.7.
    const c7 = rampColor(0.7, 3).color
    const c8 = rampColor(0.8, 3).color
    expect(c7).not.toBe(NEUTRAL)
    expect(c8).not.toBe(NEUTRAL)
    expect(c7).not.toBe(c8)
    const green = (hex: string) => parseInt(hex.slice(3, 5), 16)
    expect(green(c8)).toBeGreaterThan(green(c7))
    expect(green(c8)).toBeLessThan(green(RAMP_COLORS[6]))
  })

  it("scales with the day-adaptive span", () => {
    // span 1.5 (σ floor): +1.5 is already the extreme.
    expect(rampColor(1.5, 1.5).color).toBe(RAMP_COLORS[6])
    expect(rampColor(1.5, 3).color).not.toBe(RAMP_COLORS[6])
  })

  it("always supplies a legible ink", () => {
    for (const v of [-3, -1.2, 0, 0.4, 2.9]) {
      expect(rampColor(v, 3).ink).toMatch(/^#/)
    }
  })
})
