import { useMemo } from "react"
import type { Asset, Quote, IndicatorSummary } from "@/lib/api"
import type { AssetTypeFilter, GroupSortBy, SortDir } from "@/lib/settings"
import { getNumericValue } from "@/lib/indicator-registry"

function compareNullable(a: number | null, b: number | null): number {
  if (a == null && b == null) return 0
  if (a == null) return 1
  if (b == null) return -1
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
      let cmp = 0
      switch (sortBy) {
        case "name":
          cmp = a.symbol.localeCompare(b.symbol)
          break
        case "price":
          cmp = compareNullable(
            quotes[a.symbol]?.price ?? null,
            quotes[b.symbol]?.price ?? null,
          )
          break
        case "change_pct":
          cmp = compareNullable(
            quotes[a.symbol]?.change_percent ?? null,
            quotes[b.symbol]?.change_percent ?? null,
          )
          break
        default:
          // Indicator-based sorting: sortBy is the field name (e.g. "rsi", "macd")
          cmp = compareNullable(
            getNumericValue(indicators?.[a.symbol]?.values, sortBy),
            getNumericValue(indicators?.[b.symbol]?.values, sortBy),
          )
          break
      }
      return sortDir === "asc" ? cmp : -cmp
    })

    return sorted
  }, [assets, typeFilter, selectedTags, sortBy, sortDir, quotes, indicators])
}
