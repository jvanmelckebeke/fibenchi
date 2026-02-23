import { useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query"
import { useCallback } from "react"
import { api } from "../api"
import { keys, STALE_5MIN, STALE_24H, useInvalidatingMutation } from "./shared"

export function useAssetDetail(symbol: string, period?: string, opts?: { enabled?: boolean }) {
  return useQuery({
    queryKey: keys.assetDetail(symbol, period),
    queryFn: () => api.prices.detail(symbol, period),
    enabled: (opts?.enabled ?? true) && !!symbol,
    staleTime: STALE_5MIN, // 5 min — daily OHLCV data, SSE handles live quotes
    placeholderData: keepPreviousData,
  })
}

export function useEtfHoldings(symbol: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.etfHoldings(symbol),
    queryFn: () => api.prices.holdings(symbol),
    enabled: !!symbol && enabled,
    staleTime: STALE_24H, // cache 24h — holdings don't change often
  })
}

export function useHoldingsIndicators(symbol: string, enabled: boolean) {
  return useQuery({
    queryKey: keys.holdingsIndicators(symbol),
    queryFn: () => api.prices.holdingsIndicators(symbol),
    enabled: !!symbol && enabled,
    staleTime: STALE_5MIN, // cache 5 min
  })
}

export function useRefreshPrices(symbol: string) {
  return useInvalidatingMutation(
    (period?: string) => api.prices.refresh(symbol, period),
    [["asset-detail", symbol]],
  )
}

// Prefetch — fire on hover to warm cache before navigation
export function usePrefetchAssetDetail(period: string) {
  const qc = useQueryClient()
  return useCallback(
    (symbol: string) =>
      qc.prefetchQuery({
        queryKey: keys.assetDetail(symbol, period),
        queryFn: () => api.prices.detail(symbol, period),
        staleTime: STALE_5MIN,
      }),
    [qc, period],
  )
}
