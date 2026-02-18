import { Navigate } from "react-router-dom"
import { useGroups } from "@/lib/queries"

/**
 * Redirect /watchlist to the default Watchlist group's detail page.
 * Falls back to / if the groups haven't loaded yet.
 */
export function WatchlistRedirect() {
  const { data: groups } = useGroups()
  const defaultGroup = groups?.find((g) => g.is_default)

  if (!groups) return null // loading
  if (defaultGroup) return <Navigate to={`/groups/${defaultGroup.id}`} replace />
  return <Navigate to="/" replace />
}
