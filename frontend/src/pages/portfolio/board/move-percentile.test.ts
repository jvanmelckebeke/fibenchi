import { describe, it, expect } from "vitest"
import { MIN_WINDOW_FILL, movePercentile, moverBarWidth, windowBarFill } from "./move-percentile"

// 0, 1, 2, ..., 20: percentile = |move| * 5%.
const LINEAR = Array.from({ length: 21 }, (_, i) => i)

describe("movePercentile", () => {
  it("interpolates between quantiles", () => {
    expect(movePercentile(10, LINEAR)).toBeCloseTo(0.5)
    expect(movePercentile(2.5, LINEAR)).toBeCloseTo(0.125)
  })

  it("reads the absolute size of the move", () => {
    expect(movePercentile(-10, LINEAR)).toBeCloseTo(0.5)
  })

  it("clamps below the smallest and at or above the largest quantile", () => {
    const q = LINEAR.map((v) => v + 1)
    expect(movePercentile(0.5, q)).toBe(0)
    expect(movePercentile(1, q)).toBe(0)
    expect(movePercentile(21, q)).toBe(1)
    expect(movePercentile(500, q)).toBe(1)
  })

  it("takes the upper index across tied quantiles", () => {
    // q[0..4] = 0, q[5..9] = 3, then 4 .. 14.
    const q = [0, 0, 0, 0, 0, 3, 3, 3, 3, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
    expect(movePercentile(0, q)).toBeCloseTo(0.2)
    expect(movePercentile(3, q)).toBeCloseTo(0.45)
    // Between the top of the run (index 9) and the next quantile.
    expect(movePercentile(3.5, q)).toBeCloseTo(0.475)
  })

  it("reads a flat history as fully unusual for any move", () => {
    const flat = new Array(21).fill(0)
    expect(movePercentile(0, flat)).toBe(1)
    expect(movePercentile(0.1, flat)).toBe(1)
  })
})

describe("windowBarFill", () => {
  it("fills to the percentile", () => {
    expect(windowBarFill(movePercentile(10, LINEAR))).toBeCloseTo(0.5)
    expect(windowBarFill(1)).toBe(1)
  })

  it("keeps a stub for a real reading at the bottom of the history", () => {
    expect(windowBarFill(0)).toBe(MIN_WINDOW_FILL)
    expect(windowBarFill(0.05)).toBe(MIN_WINDOW_FILL)
  })

  it("draws an empty track without a scale", () => {
    expect(windowBarFill(null)).toBeNull()
  })
})

describe("moverBarWidth", () => {
  it("is the percentile in percent, with no stub", () => {
    expect(moverBarWidth(movePercentile(-4, LINEAR))).toBeCloseTo(20)
    expect(moverBarWidth(0)).toBe(0)
    expect(moverBarWidth(1)).toBe(100)
  })

  it("draws nothing without a scale", () => {
    expect(moverBarWidth(null)).toBe(0)
  })
})
