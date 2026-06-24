import { Layers, Plus } from "lucide-react"
import { resolveIcon } from "@/lib/icon-utils"
import { useTheses, useAddAssetToThesis, useRemoveAssetFromThesis } from "@/lib/queries"
import type { Group } from "@/lib/api"
import type { ContextAction } from "@/components/context-menu/context-actionable"

/**
 * The shared "Theses" submenu, as data: a checkbox per thesis (toggles the
 * asset's membership) plus a "New thesis…" escape hatch. Used by both the
 * group-scoped and thesis-scoped row menus.
 */
export function useThesisMembershipAction(assetId: number, onNewThesis: () => void): ContextAction {
  const { data: theses } = useTheses()
  const addToThesis = useAddAssetToThesis()
  const removeFromThesis = useRemoveAssetFromThesis()
  const list = theses ?? []

  const items: ContextAction[] = [
    ...list.map((t): ContextAction => ({
      label: t.name,
      swatch: t.color,
      checked: t.assets.some((a) => a.id === assetId),
      onToggle: (checked: boolean) =>
        checked
          ? addToThesis.mutate({ thesisId: t.id, assetId })
          : removeFromThesis.mutate({ thesisId: t.id, assetId }),
    })),
    { label: "New thesis…", icon: Plus, action: onNewThesis, separatorBefore: list.length > 0 },
  ]

  return { label: "Theses", icon: Layers, items }
}

/**
 * "Add this asset to group X" items — shared by the asset row menu's "Copy to
 * group" and the thesis-member menu's "Add to group". Groups the asset is
 * already in are shown disabled with a hint.
 */
export function groupTargetActions(
  groups: Group[],
  assetId: number,
  symbol: string,
  onAdd: (groupId: number) => void,
): ContextAction[] {
  return groups.map((g) => {
    const alreadyIn = g.assets.some((a) => a.id === assetId)
    return {
      label: g.name,
      icon: resolveIcon(g.icon),
      disabled: alreadyIn,
      hint: alreadyIn ? `${symbol} already in group` : undefined,
      action: () => onAdd(g.id),
    }
  })
}
