import { describe, it, expect } from "vitest"
import {
  RAMP_COLORS,
  boardScale,
  hasTighteningCoverage,
  pctSpan,
  rampColor,
  sigmaUnit,
  type ScaleTile,
} from "./color-scale"

const NEUTRAL = RAMP_COLORS[3]

describe("sigmaUnit — day-adaptive σ scale", () => {
  it("tightens on quiet days but floors at a ±1.5σ range", () => {
    expect(sigmaUnit([0.2, -0.3, 0.1], 3)).toBe(0.5) // dead calm → floor
    expect(sigmaUnit([2.1, -0.4], 2)).toBeCloseTo(0.7)
  })
  it("caps at the canonical ±3σ on wild days", () => {
    expect(sigmaUnit([4.2, -1.0], 2)).toBe(1)
  })
  it("defaults to the canonical scale with no readings", () => {
    expect(sigmaUnit([], 0)).toBe(1)
    expect(sigmaUnit([], 40)).toBe(1)
  })
  it("refuses to tighten onto a partial board", () => {
    // Two calm survivors out of ten tiles: the max over a subset can't exceed
    // the max over the board, so tightening here can only over-paint.
    expect(sigmaUnit([0.2, -0.3], 10)).toBe(1)
    // A stray blank on an otherwise-read board still tightens.
    expect(sigmaUnit([2.1, -0.4, 0.3, 0.1, 0.2, 0.1, 0.4, 0.2, 0.3], 10)).toBeCloseTo(0.7)
  })
})

describe("hasTighteningCoverage", () => {
  it("requires readings and near-complete coverage", () => {
    expect(hasTighteningCoverage(0, 0)).toBe(false)
    expect(hasTighteningCoverage(0, 40)).toBe(false)
    expect(hasTighteningCoverage(5, 10)).toBe(false)
    expect(hasTighteningCoverage(8, 10)).toBe(false) // just under the gate
    expect(hasTighteningCoverage(9, 10)).toBe(true)
    expect(hasTighteningCoverage(10, 10)).toBe(true)
  })
  it("holds at the boundary on a non-round board", () => {
    expect(hasTighteningCoverage(70, 78)).toBe(false)
    expect(hasTighteningCoverage(71, 78)).toBe(true)
    // The observed normal state: one warmup blank out of 78.
    expect(hasTighteningCoverage(77, 78)).toBe(true)
  })
})

describe("pctSpan — day-adaptive %-of-today scale", () => {
  it("tracks the day's biggest move within the ±2 … ±7 band", () => {
    expect(pctSpan([0.3, -0.8], 2)).toBe(2) // flat day → floor
    expect(pctSpan([4.1, -1.2], 2)).toBeCloseTo(4.1)
    expect(pctSpan([12, -3], 2)).toBe(7) // cap
    expect(pctSpan([], 0)).toBe(7)
  })
  it("holds the full span while coverage is partial", () => {
    expect(pctSpan([0.3, -0.8], 10)).toBe(7)
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

const tile = (sigma: number | null, todayPct: number | null, pending = false): ScaleTile => ({
  sigma,
  todayPct,
  reason: pending ? { kind: "pending" } : sigma == null ? { kind: "no_data" } : null,
})

describe("boardScale — the one ramp the board shares", () => {
  it("calibrates on a fully-read board", () => {
    const tiles = [tile(2.1, 3), tile(-0.4, -1), tile(0.3, 0.5)]
    const { span, unread, tightened } = boardScale(tiles, "sigma")
    expect(tightened).toBe(true)
    expect(span).toBeCloseTo(2.1) // 3 × 0.7
    expect(unread).toBe(0)
  })

  it("counts the blanks in the denominator rather than dropping them", () => {
    // Seven of ten blank: the calm survivors must not pull the ramp in.
    const tiles = [tile(0.2, 0.3), tile(-0.3, -0.4), tile(0.1, 0.2), ...Array.from({ length: 7 }, () => tile(null, null))]
    const { span, unread, tightened } = boardScale(tiles, "sigma")
    expect(tightened).toBe(false)
    expect(span).toBe(3) // canonical ±3σ, not the 1.5 the survivors would give
    expect(unread).toBe(7)
  })

  it("reads todayPct in % mode, which blanks on its own conditions", () => {
    // A tile can carry a σ and no %, or a % and no σ: the mode decides which
    // column is the reading, so each mode gates on its own coverage.
    const tiles = [tile(null, 1.2), tile(0.4, null), ...Array.from({ length: 8 }, () => tile(0.2, 0.8))]
    expect(boardScale(tiles, "pct").unread).toBe(1)
    expect(boardScale(tiles, "sigma").unread).toBe(1)
    expect(boardScale(tiles, "pct").tightened).toBe(true)
    expect(boardScale(tiles, "sigma").tightened).toBe(true)
  })

  it("reports a cold load as pending, not as a coverage collapse", () => {
    const tiles = Array.from({ length: 84 }, () => tile(null, null, true))
    const { span, unread, pending, tightened } = boardScale(tiles, "sigma")
    expect(pending).toBe(84)
    expect(unread).toBe(0) // the legend must not print "84 without a reading"
    expect(tightened).toBe(false)
    expect(span).toBe(3)
  })
})
