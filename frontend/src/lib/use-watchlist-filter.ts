import { useMemo } from "react"
import type { Asset, Quote, IndicatorSummary } from "@/lib/api"
import type { AssetTypeFilter, WatchlistSortBy, SortDir } from "@/lib/settings"

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
    sortBy: WatchlistSortBy
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
        case "rsi":
          cmp = compareNullable(
            indicators?.[a.symbol]?.rsi ?? null,
            indicators?.[b.symbol]?.rsi ?? null,
          )
          break
        case "macd":
          cmp = compareNullable(
            indicators?.[a.symbol]?.macd ?? null,
            indicators?.[b.symbol]?.macd ?? null,
          )
          break
        case "macd_signal":
          cmp = compareNullable(
            indicators?.[a.symbol]?.macd_signal ?? null,
            indicators?.[b.symbol]?.macd_signal ?? null,
          )
          break
        case "macd_hist":
          cmp = compareNullable(
            indicators?.[a.symbol]?.macd_hist ?? null,
            indicators?.[b.symbol]?.macd_hist ?? null,
          )
          break
      }
      return sortDir === "asc" ? cmp : -cmp
    })

    return sorted
  }, [assets, typeFilter, selectedTags, sortBy, sortDir, quotes, indicators])
}
