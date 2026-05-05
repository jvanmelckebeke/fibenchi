import { useQuery } from "@tanstack/react-query"
import { api } from "../api"
import { keys, STALE_24H } from "./shared"

export function useEarnings(symbol: string, enabled = true) {
  return useQuery({
    queryKey: keys.earnings(symbol),
    queryFn: () => api.prices.earnings(symbol),
    enabled: !!symbol && enabled,
    staleTime: STALE_24H,
  })
}
