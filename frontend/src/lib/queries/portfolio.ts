import { useQuery, keepPreviousData } from "@tanstack/react-query"
import { api } from "../api"
import { keys, STALE_5MIN } from "./shared"

export function usePortfolioIndex(period?: string) {
  return useQuery({
    queryKey: keys.portfolioIndex(period),
    queryFn: () => api.portfolio.index(period),
    staleTime: STALE_5MIN,
    placeholderData: keepPreviousData,
  })
}

export function usePortfolioPerformers(period?: string) {
  return useQuery({
    queryKey: keys.portfolioPerformers(period),
    queryFn: () => api.portfolio.performers(period),
    staleTime: STALE_5MIN,
    placeholderData: keepPreviousData,
  })
}
