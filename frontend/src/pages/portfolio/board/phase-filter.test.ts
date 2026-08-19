import { describe, expect, it } from "vitest"
import { applyPhaseFilter, type Phase, type Tile } from "./use-board-data"

function tile(symbol: string, phase: Phase | null): Tile {
  // Only `phase` is read by the filter; the rest of the Tile is scaffolding.
  return { symbol, phase } as Tile
}

function board(entries: [string, Phase | null][]): Map<string, Tile> {
  return new Map(entries.map(([sym, phase]) => [sym, tile(sym, phase)]))
}

describe("applyPhaseFilter", () => {
  it("returns the same map instance for 'all' (no needless re-render)", () => {
    const tiles = board([["AAPL", "closed"]])
    expect(applyPhaseFilter(tiles, "all")).toBe(tiles)
  })

  it("keeps only the trading session, not the extended windows", () => {
    const tiles = board([
      ["OPEN", "open"],
      ["PRE", "premarket"],
      ["POST", "aftermarket"],
      ["SHUT", "closed"],
    ])
    expect([...applyPhaseFilter(tiles, "open").keys()]).toEqual(["OPEN"])
  })

  it("hides tiles whose venue calendar never resolved", () => {
    const tiles = board([["KNOWN", "open"], ["MYSTERY", null]])
    expect([...applyPhaseFilter(tiles, "open").keys()]).toEqual(["KNOWN"])
  })

  it("yields an empty map overnight rather than falling back to everything", () => {
    const tiles = board([["A", "closed"], ["B", "aftermarket"]])
    expect(applyPhaseFilter(tiles, "open").size).toBe(0)
  })
})
