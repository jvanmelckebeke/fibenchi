import { useParams, Navigate } from "react-router-dom"
import { GroupPage } from "@/pages/group-page"

export function GroupDetailPage() {
  const { id } = useParams<{ id: string }>()
  const groupId = Number(id)

  if (!id || isNaN(groupId)) return <Navigate to="/" replace />

  return <GroupPage groupId={groupId} />
}
