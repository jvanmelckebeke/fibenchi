import { useState, useEffect, useMemo } from "react"
import { getAllSortableFields } from "@/lib/indicator-registry"
import { useSettings } from "@/lib/settings"

export const SORTABLE_FIELDS = getAllSortableFields()

/**
 * Reconcile a persisted column order against the current indicator registry.
 *
 * The saved order can go stale: a field may have been removed since it was
 * saved, or a new indicator (e.g. `vnr`) may have been added afterwards. We keep
 * the saved fields that still exist, then append any registry fields the saved
 * order doesn't mention — in registry order — so new indicators show up at the
 * right end automatically. An empty order therefore yields pure registry order
 * (today's behaviour), which is why the default needs no migration.
 */
export function applyColumnOrder(order: string[]): string[] {
  const known = new Set(SORTABLE_FIELDS)
  const seen = new Set<string>()
  const ordered: string[] = []
  for (const f of order) {
    // Drop unknown (removed) fields and any duplicates from corrupt storage.
    if (known.has(f) && !seen.has(f)) {
      seen.add(f)
      ordered.push(f)
    }
  }
  const rest = SORTABLE_FIELDS.filter((f) => !seen.has(f))
  return [...ordered, ...rest]
}

/** The full indicator field list in the user's persisted order (registry order by default). */
export function useOrderedIndicatorFields(): string[] {
  const { settings } = useSettings()
  const order = settings.group_table_column_order
  return useMemo(() => applyColumnOrder(order), [order])
}

/** Column identifiers for base (non-indicator) toggleable columns. */
export const BASE_COLUMN_DEFS: { key: string; label: string }[] = [
  { key: "name", label: "Name" },
  { key: "price", label: "Price" },
  { key: "change_pct", label: "Change %" },
]

/** Check whether a column is visible. Missing key = visible (opt-out model). */
export function isColumnVisible(columnSettings: Record<string, boolean>, key: string): boolean {
  return columnSettings[key] !== false
}

/** Minimum viewport width (px) for a column to be auto-shown. */
const RESPONSIVE_HIDE_BREAKPOINTS: Record<string, number> = {
  adx: 1280,
  atr_pct: 1280,
  vnr: 1280,
  avg_volume: 1280,
  atr: 1024,
  volume: 1024,
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
