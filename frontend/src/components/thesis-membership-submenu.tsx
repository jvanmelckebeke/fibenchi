import { Layers, Plus } from "lucide-react"
import {
  ContextMenuCheckboxItem,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
} from "@/components/ui/context-menu"
import { useTheses, useAddAssetToThesis, useRemoveAssetFromThesis } from "@/lib/queries"

/**
 * The "Theses" context-submenu — toggle an asset's membership across every
 * thesis, plus a "New thesis…" escape hatch. Shared by the group-scoped row menu
 * (`AssetContextMenuContent`) and the thesis-scoped one
 * (`ThesisMemberContextMenuContent`) so the two stay identical.
 */
export function ThesisMembershipSubmenu({
  assetId,
  onNewThesis,
}: {
  assetId: number
  onNewThesis: () => void
}) {
  const { data: theses } = useTheses()
  const addToThesis = useAddAssetToThesis()
  const removeFromThesis = useRemoveAssetFromThesis()
  const thesisList = theses ?? []

  return (
    <ContextMenuSub>
      <ContextMenuSubTrigger className="gap-2">
        <Layers className="h-4 w-4" />
        Theses
      </ContextMenuSubTrigger>
      <ContextMenuSubContent>
        {thesisList.map((t) => {
          const member = t.assets.some((a) => a.id === assetId)
          return (
            <ContextMenuCheckboxItem
              key={t.id}
              checked={member}
              onSelect={(e) => e.preventDefault()}
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
        })}
        {thesisList.length > 0 && <ContextMenuSeparator />}
        <ContextMenuItem onClick={onNewThesis}>
          <Plus className="h-4 w-4" />
          New thesis&hellip;
        </ContextMenuItem>
      </ContextMenuSubContent>
    </ContextMenuSub>
  )
}
