import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { api, type AssetCreate, type SymbolSearchResult } from "../api"
import { keys, STALE_1MIN, STALE_5MIN, useInvalidatingMutation } from "./shared"

export function useAssets() {
  return useQuery({ queryKey: keys.assets, queryFn: api.assets.list, staleTime: STALE_5MIN })
}

export function useCreateAsset() {
  return useInvalidatingMutation(
    (data: AssetCreate) => api.assets.create(data),
    [keys.assets, keys.groups],
  )
}

// Search
export function useLocalSearch(query: string) {
  return useQuery<SymbolSearchResult[]>({
    queryKey: keys.symbolSearchLocal(query),
    queryFn: () => api.searchLocal(query),
    enabled: query.length >= 1,
    staleTime: STALE_1MIN,
    placeholderData: keepPreviousData,
  })
}

export function useYahooSearch(query: string) {
  return useQuery<SymbolSearchResult[]>({
    queryKey: keys.symbolSearchYahoo(query),
    queryFn: () => api.searchYahoo(query),
    enabled: query.length >= 1,
    staleTime: STALE_1MIN,
    placeholderData: keepPreviousData,
  })
}
