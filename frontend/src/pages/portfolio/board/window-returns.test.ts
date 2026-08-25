import { describe, it, expect } from "vitest"
import { windowPct, type WindowBounds } from "./window-returns"

// A window opening 2026-07-27, with the grace running to 2026-08-01.
const BOUNDS: WindowBounds = { start: "2026-07-27", latestBaseline: "2026-08-01" }

const series = (...entries: [string, number][]) =>
  entries.map(([date, close]) => ({ date, close }))

describe("windowPct", () => {
  it("measures from the last close at or before the window start", () => {
    const pts = series(["2026-07-24", 100], ["2026-07-27", 110], ["2026-08-20", 121])
    // Two candidates precede the start; the later one wins.
    expect(windowPct(pts, 121, BOUNDS)).toBeCloseTo(10)
  })

  it("takes the reopening session when the window starts on a closed day", () => {
    // The 27th is a Sunday here: the series jumps the weekend.
    const pts = series(["2026-07-28", 100], ["2026-08-20", 105])
    expect(windowPct(pts, 105, BOUNDS)).toBeCloseTo(5)
  })

  it("withholds when the series begins well after the window", () => {
    // A recently added asset — past the grace, so there is no honest baseline.
    const pts = series(["2026-08-10", 100], ["2026-08-20", 130])
    expect(windowPct(pts, 130, BOUNDS)).toBeNull()
  })

  it("measures against the live price, not the last stored close", () => {
    const pts = series(["2026-07-27", 100], ["2026-08-20", 110])
    expect(windowPct(pts, 120, BOUNDS)).toBeCloseTo(20)
  })

  it("withholds on an empty series or a zero baseline", () => {
    expect(windowPct([], 100, BOUNDS)).toBeNull()
    expect(windowPct(series(["2026-07-27", 0], ["2026-08-20", 5]), 5, BOUNDS)).toBeNull()
  })
})
