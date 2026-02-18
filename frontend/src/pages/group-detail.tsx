import { useParams } from "react-router-dom"
import { WatchlistPage } from "@/pages/watchlist"

export function GroupDetailPage() {
  const { id } = useParams<{ id: string }>()
  const groupId = Number(id)

  return <WatchlistPage groupId={groupId} />
}
