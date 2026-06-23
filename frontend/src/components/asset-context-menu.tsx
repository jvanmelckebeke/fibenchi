import { ArrowRightLeft, Copy, Pencil, Trash2 } from "lucide-react"
import { resolveIcon } from "@/lib/icon-utils"
import { ContextActionsContent, type ContextAction } from "@/components/context-actionable"
import { useThesisMembershipAction } from "@/components/thesis-membership-action"
import { useGroups, useAddAssetsToGroup, useRemoveAssetFromGroup } from "@/lib/queries"

interface AssetContextMenuContentProps {
  groupId: number
  assetId: number
  symbol: string
  onEdit: () => void
  onRemove: () => void
  onNewThesis: () => void
}

/** Group-scoped row menu: move/copy between groups, toggle theses, edit, remove. */
export function AssetContextMenuContent({
  groupId,
  assetId,
  symbol,
  onEdit,
  onRemove,
  onNewThesis,
}: AssetContextMenuContentProps) {
  const { data: groups } = useGroups()
  const addToGroup = useAddAssetsToGroup()
  const removeFromGroup = useRemoveAssetFromGroup()
  const thesisAction = useThesisMembershipAction(assetId, onNewThesis)

  const otherGroups = groups?.filter((g) => g.id !== groupId) ?? []
  const isInGroup = (g: { assets: { id: number }[] }) => g.assets.some((a) => a.id === assetId)

  const groupActions: ContextAction[] =
    otherGroups.length > 0
      ? [
          {
            label: "Move to group",
            icon: ArrowRightLeft,
            items: otherGroups.map((g): ContextAction => ({
              label: g.name,
              icon: resolveIcon(g.icon),
              action: () => {
                removeFromGroup.mutate({ groupId, assetId })
                addToGroup.mutate({ groupId: g.id, assetIds: [assetId] })
              },
            })),
          },
          {
            label: "Copy to group",
            icon: Copy,
            items: otherGroups.map((g): ContextAction => ({
              label: g.name,
              icon: resolveIcon(g.icon),
              disabled: isInGroup(g),
              hint: isInGroup(g) ? `${symbol} already in group` : undefined,
              action: () => addToGroup.mutate({ groupId: g.id, assetIds: [assetId] }),
            })),
          },
        ]
      : []

  const actions: ContextAction[] = [
    ...groupActions,
    { ...thesisAction, separatorBefore: otherGroups.length > 0 },
    { label: "Edit asset…", icon: Pencil, action: onEdit, separatorBefore: true },
    {
      label: "Remove from group",
      icon: Trash2,
      action: onRemove,
      destructive: true,
      separatorBefore: true,
    },
  ]

  return <ContextActionsContent actions={actions} />
}
