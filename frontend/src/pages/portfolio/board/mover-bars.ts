// A Movers row's bar is the row's % against the largest |%| the card shows, so
// bar length tracks the number printed beside it. The tiles' own-history
// percentile answers a different question and would rank rows one way while
// the bars said another.

/** Largest absolute move among `pcts`, or 0 when there are none. */
export function maxAbsMove(pcts: number[]): number {
  return pcts.reduce((m, p) => Math.max(m, Math.abs(p)), 0)
}

/** Width of a Movers row's background bar in percent of the row. */
export function moverBarWidth(pct: number, maxAbs: number): number {
  return maxAbs > 0 ? (Math.abs(pct) / maxAbs) * 100 : 0
}
