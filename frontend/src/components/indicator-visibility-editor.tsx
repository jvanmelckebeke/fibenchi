import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  INDICATOR_REGISTRY,
  type IndicatorDescriptor,
  type IndicatorCategory,
  type Placement,
} from "@/lib/indicator-registry"

const CATEGORY_ORDER: IndicatorCategory[] = ["technical", "volatility", "market_data", "fundamentals"]
const CATEGORY_LABELS: Record<IndicatorCategory, string> = {
  technical: "Technical",
  volatility: "Volatility",
  market_data: "Market Data",
  fundamentals: "Fundamentals",
}

const PLACEMENT_COLS: { placement: Placement; label: string }[] = [
  { placement: "group_table", label: "Table" },
  { placement: "group_card", label: "Card" },
  { placement: "detail_chart", label: "Chart" },
  { placement: "detail_card", label: "Detail" },
  { placement: "detail_stats", label: "Stats" },
]

interface IndicatorVisibilityEditorProps {
  visibility: Record<string, Placement[]>
  onChange: (visibility: Record<string, Placement[]>) => void
}

export function IndicatorVisibilityEditor({ visibility, onChange }: IndicatorVisibilityEditorProps) {
  const [open, setOpen] = useState(false)

  const grouped = new Map<IndicatorCategory, IndicatorDescriptor[]>()
  for (const desc of INDICATOR_REGISTRY) {
    const list = grouped.get(desc.category) ?? []
    list.push(desc)
    grouped.set(desc.category, list)
  }

  function getActivePlacements(id: string): Placement[] {
    const desc = INDICATOR_REGISTRY.find((d) => d.id === id)
    if (!desc) return []
    return visibility[id] ?? desc.defaults
  }

  function togglePlacement(id: string, placement: Placement, enabled: boolean) {
    const desc = INDICATOR_REGISTRY.find((d) => d.id === id)
    if (!desc) return
    const current = visibility[id] ?? [...desc.defaults]
    const next = enabled
      ? [...new Set([...current, placement])]
      : current.filter((p) => p !== placement)
    onChange({ ...visibility, [id]: next })
  }

  function resetAll() {
    onChange({})
  }

  const hasCustom = Object.keys(visibility).length > 0

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-full">
          Configure Indicator Visibility
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Indicator Visibility</DialogTitle>
        </DialogHeader>

        {/* Column headers */}
        <div className="space-y-4">
          <div className="grid items-center gap-x-2" style={{ gridTemplateColumns: `1fr repeat(${PLACEMENT_COLS.length}, 56px)` }}>
            <div />
            {PLACEMENT_COLS.map((col) => (
              <span key={col.placement} className="text-[11px] text-muted-foreground text-center font-medium">
                {col.label}
              </span>
            ))}
          </div>

          {CATEGORY_ORDER.filter((cat) => grouped.has(cat)).map((cat) => (
            <div key={cat}>
              <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-1.5">
                {CATEGORY_LABELS[cat]}
              </h4>
              <div className="space-y-0.5">
                {grouped.get(cat)!.map((desc) => {
                  const active = getActivePlacements(desc.id)
                  return (
                    <div
                      key={desc.id}
                      className="grid items-center gap-x-2 py-1.5 rounded hover:bg-muted/50"
                      style={{ gridTemplateColumns: `1fr repeat(${PLACEMENT_COLS.length}, 56px)` }}
                    >
                      <span className="text-sm font-medium pl-1">{desc.label}</span>
                      {PLACEMENT_COLS.map((col) => {
                        const capable = desc.capabilities.includes(col.placement)
                        const checked = capable && active.includes(col.placement)
                        return (
                          <div key={col.placement} className="flex justify-center">
                            {capable ? (
                              <Checkbox
                                checked={checked}
                                onCheckedChange={(v) =>
                                  togglePlacement(desc.id, col.placement, v === true)
                                }
                              />
                            ) : (
                              <span className="text-muted-foreground/30">—</span>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        <DialogFooter>
          {hasCustom && (
            <Button variant="ghost" size="sm" onClick={resetAll}>
              Reset all to defaults
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
