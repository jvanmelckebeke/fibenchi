import { ArrowRightLeft, Copy, Layers, Pencil, Trash2 } from "lucide-react"
import { resolveIcon } from "@/lib/icon-utils"
import {
  ContextMenuCheckboxItem,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
} from "@/components/ui/context-menu"
import {
  useGroups,
  useAddAssetsToGroup,
  useRemoveAssetFromGroup,
  useTheses,
  useAddAssetToThesis,
  useRemoveAssetFromThesis,
} from "@/lib/queries"

interface AssetContextMenuContentProps {
  groupId: number
  assetId: number
  symbol: string
  onEdit: () => void
  onRemove: () => void
}

export function AssetContextMenuContent({
  groupId,
  assetId,
  symbol,
  onEdit,
  onRemove,
}: AssetContextMenuContentProps) {
  const { data: groups } = useGroups()
  const { data: theses } = useTheses()
  const addToGroup = useAddAssetsToGroup()
  const removeFromGroup = useRemoveAssetFromGroup()
  const addToThesis = useAddAssetToThesis()
  const removeFromThesis = useRemoveAssetFromThesis()

  const otherGroups = groups?.filter((g) => g.id !== groupId) ?? []
  const thesisList = theses ?? []

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
      <ContextMenuSub>
        <ContextMenuSubTrigger className="gap-2">
          <Layers className="h-4 w-4" />
          Theses
        </ContextMenuSubTrigger>
        <ContextMenuSubContent>
          {thesisList.length === 0 ? (
            <ContextMenuItem disabled>No theses yet</ContextMenuItem>
          ) : (
            thesisList.map((t) => {
              const member = t.assets.some((a) => a.id === assetId)
              return (
                <ContextMenuCheckboxItem
                  key={t.id}
                  checked={member}
                  onCheckedChange={(checked) =>
                    checked
                      ? addToThesis.mutate({ thesisId: t.id, assetId })
                      : removeFromThesis.mutate({ thesisId: t.id, assetId })
                  }
                >
                  <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: t.color }} />
                  {t.name}
                </ContextMenuCheckboxItem>
              )
            })
          )}
        </ContextMenuSubContent>
      </ContextMenuSub>
      <ContextMenuSeparator />
      <ContextMenuItem onClick={onEdit}>
        <Pencil className="h-4 w-4" />
        Edit asset…
      </ContextMenuItem>
      <ContextMenuSeparator />
      <ContextMenuItem variant="destructive" onClick={onRemove}>
        <Trash2 className="h-4 w-4" />
        Remove from group
      </ContextMenuItem>
    </ContextMenuContent>
  )
}
