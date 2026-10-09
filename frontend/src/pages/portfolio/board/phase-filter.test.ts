import { describe, expect, it } from "vitest"
import { applyPhaseFilter, relevanceCutoff, type Phase, type Tile } from "./use-board-data"

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

// Local wall-clock instants, so the cases read in the viewer's own time
// whatever zone the test runner sits in.
const at = (day: number, hour: number, minute = 0) => new Date(2026, 9, day, hour, minute)

function venue(symbol: string, phase: Phase | null, lastClose: Date | null): [string, Tile] {
  return [symbol, { symbol, phase, lastClose: lastClose?.toISOString() ?? null } as Tile]
}

// Friday 9 Oct 2026, CEST. Asia closed this morning, the US last night.
const book = new Map([
  venue("ASIA", "closed", at(9, 8, 30)),
  venue("EU", "open", at(8, 17, 30)),
  venue("US", "premarket", at(8, 22)),
  venue("CRYPTO", "open", null),
])

describe("relevanceCutoff", () => {
  it("is today's 04:00 from 04:00 on", () => {
    expect(relevanceCutoff(at(9, 13))).toEqual(at(9, 4))
    expect(relevanceCutoff(at(9, 4))).toEqual(at(9, 4))
  })

  it("is yesterday's 04:00 before 04:00", () => {
    expect(relevanceCutoff(at(10, 1))).toEqual(at(9, 4))
  })
})

describe("applyPhaseFilter relevant", () => {
  it("at 13:00 hides the US session that closed last night", () => {
    expect([...applyPhaseFilter(book, "relevant", at(9, 13)).keys()]).toEqual([
      "ASIA",
      "EU",
      "CRYPTO",
    ])
  })

  it("at 23:00 keeps everything that closed today", () => {
    const evening = new Map([
      venue("ASIA", "closed", at(9, 8, 30)),
      venue("EU", "closed", at(9, 17, 30)),
      venue("US", "aftermarket", at(9, 22)),
    ])
    expect(applyPhaseFilter(evening, "relevant", at(9, 23)).size).toBe(3)
    // Still there at 01:00, before Asia reopens.
    expect(applyPhaseFilter(evening, "relevant", at(10, 1)).size).toBe(3)
    // Gone once the night is over.
    expect(applyPhaseFilter(evening, "relevant", at(10, 5)).size).toBe(0)
  })

  it("hides a closed venue whose last close is unknown", () => {
    const tiles = new Map([venue("MYSTERY", "closed", null), venue("NONE", null, null)])
    expect(applyPhaseFilter(tiles, "relevant", at(9, 13)).size).toBe(0)
  })
})
