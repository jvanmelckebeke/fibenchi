import { useParams } from "react-router-dom"
import { GroupPage } from "@/pages/group-page"

export function GroupDetailPage() {
  const { id } = useParams<{ id: string }>()
  const groupId = Number(id)

  return <GroupPage groupId={groupId} />
}
