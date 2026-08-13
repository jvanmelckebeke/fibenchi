import { describe, it, expect } from "vitest"
import { packSections } from "./paging"
import type { BoardSection, Tile } from "./use-board-data"

const tile = (symbol: string) => ({ symbol }) as Tile
const section = (key: string, n: number): BoardSection => ({
  key,
  title: key,
  accent: null,
  tiles: Array.from({ length: n }, (_, i) => tile(`${key}${i}`)),
})

// 10 columns, 65px rows, 40px headers.
const M = { cols: 10, rowPx: 65, headerPx: 40, availPx: 400 }

describe("packSections", () => {
  it("keeps everything on one page when it fits", () => {
    // 2 sections × (40 + 1×65) = 210 ≤ 400
    const pages = packSections([section("a", 8), section("b", 10)], M)
    expect(pages).toHaveLength(1)
    expect(pages[0].map((s) => s.key)).toEqual(["a", "b"])
  })

  it("never splits a section across pages", () => {
    // a: 40+2×65=170, b: 40+2×65=170, c: 40+1×65=105 → a+b=340 fits, c overflows.
    const pages = packSections([section("a", 12), section("b", 15), section("c", 4)], M)
    expect(pages).toHaveLength(2)
    expect(pages[0].map((s) => s.key)).toEqual(["a", "b"])
    expect(pages[1].map((s) => s.key)).toEqual(["c"])
  })

  it("gives an oversized section its own page instead of splitting", () => {
    // huge: 40+7×65=495 > 400 — still one whole page.
    const pages = packSections([section("a", 5), section("huge", 70), section("b", 5)], M)
    expect(pages).toHaveLength(3)
    expect(pages[1].map((s) => s.key)).toEqual(["huge"])
  })

  it("handles empty input and guards a zero column count", () => {
    expect(packSections([], M)).toEqual([])
    const pages = packSections([section("a", 3)], { ...M, cols: 0 })
    expect(pages).toHaveLength(1) // cols clamps to 1 instead of dividing by zero
  })
})
