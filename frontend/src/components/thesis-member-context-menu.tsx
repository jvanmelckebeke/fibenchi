import { FolderPlus, Pencil, Trash2 } from "lucide-react"
import { resolveIcon } from "@/lib/icon-utils"
import {
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
} from "@/components/ui/context-menu"
import { useGroups, useAddAssetsToGroup, useRemoveAssetFromThesis } from "@/lib/queries"
import { ThesisMembershipSubmenu } from "@/components/thesis-membership-submenu"

interface ThesisMemberContextMenuContentProps {
  thesisId: number
  assetId: number
  symbol: string
  onEdit: () => void
  onNewThesis: () => void
}

/**
 * Row context menu for the all-theses page, where there is no single "current
 * group". Unlike the group menu it offers "Add to group" (not Move/Copy/Remove)
 * and a destructive "Remove from this thesis" instead of "Remove from group".
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
  const groupList = groups ?? []

  const isInGroup = (group: { assets: { id: number }[] }) =>
    group.assets.some((a) => a.id === assetId)

  return (
    <ContextMenuContent>
      <ContextMenuSub>
        <ContextMenuSubTrigger className="gap-2">
          <FolderPlus className="h-4 w-4" />
          Add to group
        </ContextMenuSubTrigger>
        <ContextMenuSubContent>
          {groupList.map((g) => {
            const alreadyIn = isInGroup(g)
            const Icon = resolveIcon(g.icon)
            return (
              <ContextMenuItem
                key={g.id}
                disabled={alreadyIn}
                onClick={() => addToGroup.mutate({ groupId: g.id, assetIds: [assetId] })}
              >
                <Icon className="h-4 w-4" />
                {g.name}
                {alreadyIn && (
                  <span className="ml-auto text-xs text-muted-foreground">
                    {symbol} already in group
                  </span>
                )}
              </ContextMenuItem>
            )
          })}
        </ContextMenuSubContent>
      </ContextMenuSub>
      <ThesisMembershipSubmenu assetId={assetId} onNewThesis={onNewThesis} />
      <ContextMenuSeparator />
      <ContextMenuItem onClick={onEdit}>
        <Pencil className="h-4 w-4" />
        Edit asset…
      </ContextMenuItem>
      <ContextMenuSeparator />
      <ContextMenuItem
        variant="destructive"
        onClick={() => removeFromThesis.mutate({ thesisId, assetId })}
      >
        <Trash2 className="h-4 w-4" />
        Remove from this thesis
      </ContextMenuItem>
    </ContextMenuContent>
  )
}
