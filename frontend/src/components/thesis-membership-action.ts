import { Layers, Plus } from "lucide-react"
import { useTheses, useAddAssetToThesis, useRemoveAssetFromThesis } from "@/lib/queries"
import type { ContextAction } from "@/components/context-actionable"

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
