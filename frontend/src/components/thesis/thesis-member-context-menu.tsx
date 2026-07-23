import { FolderPlus, Pencil, Trash2 } from "lucide-react"
import { ContextActionsContent, type ContextAction } from "@/components/context-menu/context-actionable"
import { useThesisMembershipAction, groupTargetActions } from "@/components/context-menu/menu-actions"
import { useGroups, useAddAssetsToGroup, useRemoveAssetFromThesis } from "@/lib/queries"

interface ThesisMemberContextMenuContentProps {
  thesisId: number
  assetId: number
  symbol: string
  onEdit: () => void
  onNewThesis: () => void
}

/**
 * Row menu for the all-theses page, where there is no single "current group".
 * Offers "Add to group" (not Move/Copy/Remove) and a destructive "Remove from
 * this thesis".
 */
export function ThesisMemberContextMenuContent({
  thesisId,
  assetId,
  symbol,
  onEdit,
  onNewThesis,
}: ThesisMemberContextMenuContentProps) {
  const { data: groups } = useGroups()
  const addToGroup = useAddAssetsToGroup()
  const removeFromThesis = useRemoveAssetFromThesis()
  const thesisAction = useThesisMembershipAction(assetId, onNewThesis)
  const groupList = groups ?? []

  const actions: ContextAction[] = [
    {
      label: "Add to group",
      icon: FolderPlus,
      items: groupTargetActions(groupList, assetId, symbol, (gid) =>
        addToGroup.mutate({ groupId: gid, assetIds: [assetId] }),
      ),
    },
    thesisAction,
    { label: "Edit asset…", icon: Pencil, action: onEdit, separatorBefore: true },
    {
      label: "Remove from this thesis",
      icon: Trash2,
      action: () => removeFromThesis.mutate({ thesisId, assetId }),
      destructive: true,
      separatorBefore: true,
    },
  ]

  return <ContextActionsContent actions={actions} />
}
