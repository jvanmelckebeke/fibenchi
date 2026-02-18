import { useParams } from "react-router-dom"
import { WatchlistPage } from "@/pages/watchlist"
import { useGroup } from "@/lib/queries"

/**
 * Group detail page — renders the full watchlist-quality view for a specific group.
 *
 * For now, this delegates to the WatchlistPage which shows all assets.
 * Issue #209 will make this group-aware (show only the group's assets,
 * use group-specific sparklines/indicators).
 */
export function GroupDetailPage() {
  const { id } = useParams<{ id: string }>()
  const groupId = Number(id)
  const { data: group } = useGroup(groupId)

  // Pass group context via the page — for now, WatchlistPage shows all grouped assets.
  // #209 will refactor WatchlistPage to accept a group prop.
  return <WatchlistPage groupName={group?.name} />
}
