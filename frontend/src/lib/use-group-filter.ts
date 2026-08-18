import { useMemo } from "react"
import type { Asset, Quote, IndicatorSummary } from "@/lib/api"
import type { AssetTypeFilter, GroupSortBy, SortDir } from "@/lib/settings"
import { getNumericValue } from "@/lib/indicator-registry"
import { resolveSigma, sigmaSortKey } from "@/lib/sigma"

/** A row's value for a given sort field: number for metrics, string for "name". */
export type SortValue = number | string | null

/**
 * Resolve the sortable value for an asset under `sortBy`, using the same sources
 * the table renders from: live SSE quote for price/change, indicator snapshot for
 * everything else. Shared so derived orderings (e.g. thesis-block averages) can't
 * drift from the row sort.
 */
export function getSortValue(
  asset: Asset,
  sortBy: GroupSortBy,
  quotes: Record<string, Quote>,
  indicators?: Record<string, IndicatorSummary>,
): SortValue {
  switch (sortBy) {
    case "name":
      return asset.symbol
    case "price":
      return quotes[asset.symbol]?.price ?? null
    case "change_pct":
      return quotes[asset.symbol]?.change_percent ?? null
    default: {
      const summary = indicators?.[asset.symbol]
      // Sort by exactly what the row renders — same resolver, so a blanked
      // cell sorts as "no value" and can never order by a number the user
      // isn't being shown.
      if (sortBy === "vnr") {
        return sigmaSortKey(resolveSigma(quotes[asset.symbol], summary))
      }
      return getNumericValue(summary?.values, sortBy)
    }
  }
}

/** Ascending comparator for {@link SortValue}: nulls last, strings via locale. */
export function compareSortValues(a: SortValue, b: SortValue): number {
  if (a == null && b == null) return 0
  if (a == null) return 1
  if (b == null) return -1
  if (typeof a === "string" || typeof b === "string") {
    return String(a).localeCompare(String(b))
  }
  return a - b
}

export function useFilteredSortedAssets(
  assets: Asset[] | undefined,
  opts: {
    typeFilter: AssetTypeFilter
    selectedTags: number[]
    sortBy: GroupSortBy
    sortDir: SortDir
    quotes: Record<string, Quote>
    indicators?: Record<string, IndicatorSummary>
  },
): Asset[] | undefined {
  const { typeFilter, selectedTags, sortBy, sortDir, quotes, indicators } = opts

  return useMemo(() => {
    if (!assets) return undefined

    let filtered = assets
    if (typeFilter !== "all") {
      filtered = filtered.filter((a) => a.type === typeFilter)
    }
    if (selectedTags.length > 0) {
      filtered = filtered.filter((a) =>
        a.tags.some((t) => selectedTags.includes(t.id))
      )
    }

    const sorted = [...filtered].sort((a, b) => {
      const cmp = compareSortValues(
        getSortValue(a, sortBy, quotes, indicators),
        getSortValue(b, sortBy, quotes, indicators),
      )
      return sortDir === "asc" ? cmp : -cmp
    })

    return sorted
  }, [assets, typeFilter, selectedTags, sortBy, sortDir, quotes, indicators])
}
