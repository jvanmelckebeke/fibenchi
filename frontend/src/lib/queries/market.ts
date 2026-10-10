import { useQuery } from "@tanstack/react-query"
import { api } from "../api"
import { keys, STALE_1MIN, STALE_5MIN } from "./shared"

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

/** Each tracked symbol's own distribution of window moves, for the board's
 * move bars. The server recomputes it only when a stored close changes. */
export function useMoveScales() {
  return useQuery({
    queryKey: keys.moveScales,
    queryFn: api.moveScales.list,
    staleTime: STALE_5MIN,
  })
}
