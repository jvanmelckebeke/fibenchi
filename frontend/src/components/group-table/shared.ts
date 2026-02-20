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
