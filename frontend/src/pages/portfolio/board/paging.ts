// Section-preserving pagination for the board: pages are packed greedily
// with whole sections (a group never splits mid-page), sized against the
// actual pixel budget of the viewport so "one page = one screenful" holds
// at any window size.

import type { BoardSection } from "./use-board-data"

export interface PackMetrics {
  /** Tile columns that fit the board width. */
  cols: number
  /** Height of one tile row incl. gap. */
  rowPx: number
  /** Height of a section header incl. its margins. */
  headerPx: number
  /** Vertical pixels available for tiles before the fold. */
  availPx: number
}

/** Greedy pack: sections flow into the current page until the next one
 * would overflow the pixel budget. A section taller than a whole page gets
 * its own page (and scrolls) rather than being split — splitting a group
 * across pages would misrepresent its size. */
export function packSections(sections: BoardSection[], m: PackMetrics): BoardSection[][] {
  const cols = Math.max(1, m.cols)
  const pages: BoardSection[][] = []
  let current: BoardSection[] = []
  let used = 0
  for (const s of sections) {
    const cost = m.headerPx + Math.ceil(s.tiles.length / cols) * m.rowPx
    if (current.length > 0 && used + cost > m.availPx) {
      pages.push(current)
      current = []
      used = 0
    }
    current.push(s)
    used += cost
  }
  if (current.length > 0) pages.push(current)
  return pages
}
