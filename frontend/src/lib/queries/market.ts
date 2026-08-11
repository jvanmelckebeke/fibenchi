import { useQuery } from "@tanstack/react-query"
import { api } from "../api"
import { keys, STALE_1MIN } from "./shared"

/** Scheduled venue phases (calendar-derived). Refetches every minute so the
 * board's phase dots flip on schedule even without a live quote feed. */
export function useMarketPhases() {
  return useQuery({
    queryKey: keys.marketPhases,
    queryFn: api.market.phases,
    staleTime: STALE_1MIN,
    refetchInterval: STALE_1MIN,
  })
}
