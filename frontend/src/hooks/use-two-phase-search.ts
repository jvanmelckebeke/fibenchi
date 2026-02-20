import { useMemo } from "react"
import { useLocalSearch, useYahooSearch } from "@/lib/queries"
import { useDebouncedValue } from "@/hooks/use-debounced-value"
import type { SymbolSearchResult } from "@/lib/api"

export interface TwoPhaseSearchResult {
  localResults: SymbolSearchResult[] | undefined
  yahooResults: SymbolSearchResult[] | undefined
  yahooLoading: boolean
  allResults: SymbolSearchResult[]
}

/**
 * Two-phase symbol search: local DB results appear near-instantly (100ms debounce),
 * Yahoo Finance results load asynchronously below (400ms debounce, deduped by backend).
 */
export function useTwoPhaseSearch(query: string): TwoPhaseSearchResult {
  const localQuery = useDebouncedValue(query, 100)
  const yahooQuery = useDebouncedValue(query, 400)

  const { data: localResults } = useLocalSearch(localQuery)
  const { data: yahooResults, isFetching: yahooLoading } = useYahooSearch(yahooQuery)

  const allResults = useMemo(() => {
    const combined: SymbolSearchResult[] = []
    if (localResults) combined.push(...localResults)
    if (yahooResults) combined.push(...yahooResults)
    return combined
  }, [localResults, yahooResults])

  return { localResults, yahooResults, yahooLoading, allResults }
}
