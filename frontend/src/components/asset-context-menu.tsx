import { ArrowRightLeft, Copy, Trash2 } from "lucide-react"
import { resolveIcon } from "@/lib/icon-utils"
import {
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
} from "@/components/ui/context-menu"
import { useGroups, useAddAssetsToGroup, useRemoveAssetFromGroup } from "@/lib/queries"

interface AssetContextMenuContentProps {
  groupId: number
  assetId: number
  symbol: string
  onRemove: () => void
}

export function AssetContextMenuContent({
  groupId,
  assetId,
  symbol,
  onRemove,
}: AssetContextMenuContentProps) {
  const { data: groups } = useGroups()
  const addToGroup = useAddAssetsToGroup()
  const removeFromGroup = useRemoveAssetFromGroup()

  const otherGroups = groups?.filter((g) => g.id !== groupId) ?? []

  const handleMove = (targetGroupId: number) => {
    removeFromGroup.mutate({ groupId, assetId })
    addToGroup.mutate({ groupId: targetGroupId, assetIds: [assetId] })
  }

  const handleCopy = (targetGroupId: number) => {
    addToGroup.mutate({ groupId: targetGroupId, assetIds: [assetId] })
  }

  const isInGroup = (group: { assets: { id: number }[] }) =>
    group.assets.some((a) => a.id === assetId)

  return (
    <ContextMenuContent>
      {otherGroups.length > 0 && (
        <>
          <ContextMenuSub>
            <ContextMenuSubTrigger className="gap-2">
              <ArrowRightLeft className="h-4 w-4" />
              Move to group
            </ContextMenuSubTrigger>
            <ContextMenuSubContent>
              {otherGroups.map((g) => {
                const Icon = resolveIcon(g.icon)
                return (
                  <ContextMenuItem key={g.id} onClick={() => handleMove(g.id)}>
                    <Icon className="h-4 w-4" />
                    {g.name}
                  </ContextMenuItem>
                )
              })}
            </ContextMenuSubContent>
          </ContextMenuSub>
          <ContextMenuSub>
            <ContextMenuSubTrigger className="gap-2">
              <Copy className="h-4 w-4" />
              Copy to group
            </ContextMenuSubTrigger>
            <ContextMenuSubContent>
              {otherGroups.map((g) => {
                const alreadyIn = isInGroup(g)
                const Icon = resolveIcon(g.icon)
                return (
                  <ContextMenuItem
                    key={g.id}
                    disabled={alreadyIn}
                    onClick={() => handleCopy(g.id)}
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
          <ContextMenuSeparator />
        </>
      )}
      <ContextMenuItem variant="destructive" onClick={onRemove}>
        <Trash2 className="h-4 w-4" />
        Remove from group
      </ContextMenuItem>
    </ContextMenuContent>
  )
}
