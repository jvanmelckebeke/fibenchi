import { describe, it, expect } from "vitest"
import { maxAbsMove, moverBarWidth } from "./mover-bars"

describe("moverBarWidth", () => {
  // The 1wk card from the bug report: gainers and losers share one scale.
  const shown = [23.84, 7.83, 7.3, 7.13, 6.74, -27, -25.47, -22.51, -21.07, -19.39]
  const max = maxAbsMove(shown)

  it("gives the largest move a full bar, either sign", () => {
    expect(max).toBe(27)
    expect(moverBarWidth(-27, max)).toBe(100)
  })

  it("orders bars the way the printed % orders rows", () => {
    const widths = shown.map((p) => moverBarWidth(p, max))
    expect(widths[0]).toBeCloseTo(88.3, 1)
    expect(widths[0]).toBeGreaterThan(widths[1])
    expect(widths[7]).toBeGreaterThan(widths[8])
  })

  it("draws nothing when no row moved", () => {
    expect(maxAbsMove([])).toBe(0)
    expect(moverBarWidth(0, 0)).toBe(0)
  })
})
