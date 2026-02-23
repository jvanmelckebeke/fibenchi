import { useState, useEffect } from "react"
import { getAllSortableFields, isIndicatorVisible } from "@/lib/indicator-registry"

export const SORTABLE_FIELDS = getAllSortableFields()

/** Column identifiers for base (non-indicator) toggleable columns. */
export const BASE_COLUMN_DEFS: { key: string; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "price", label: "Price" },
  { key: "change_pct", label: "Change %" },
]

/** Check whether a column is visible. Missing key = visible (opt-out model). */
export function isColumnVisible(columnSettings: Record<string, boolean>, key: string): boolean {
  return isIndicatorVisible(columnSettings, key)
}

/** Minimum viewport width (px) for a column to be auto-shown. */
const RESPONSIVE_HIDE_BREAKPOINTS: Record<string, number> = {
  adx: 1280,
  atr_pct: 1280,
  atr: 1024,
  macd: 768,
  rsi: 640,
}

function computeHidden(): Set<string> {
  const width = typeof window !== "undefined" ? window.innerWidth : Infinity
  const result = new Set<string>()
  for (const [key, minWidth] of Object.entries(RESPONSIVE_HIDE_BREAKPOINTS)) {
    if (width < minWidth) result.add(key)
  }
  return result
}

/** Returns the set of column keys that are auto-hidden at the current viewport width. */
export function useResponsiveHidden(): Set<string> {
  const [hidden, setHidden] = useState(computeHidden)

  useEffect(() => {
    const breakpoints = [...new Set(Object.values(RESPONSIVE_HIDE_BREAKPOINTS))].sort()
    const queries = breakpoints.map((bp) => window.matchMedia(`(min-width: ${bp}px)`))
    const update = () => setHidden(computeHidden())
    for (const mq of queries) mq.addEventListener("change", update)
    return () => {
      for (const mq of queries) mq.removeEventListener("change", update)
    }
  }, [])

  return hidden
}
