import { useState } from "react"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
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

const PLACEMENT_LABELS: Record<Placement, string> = {
  group_table: "Group table",
  group_card: "Group card",
  detail_chart: "Detail chart",
  detail_card: "Detail card",
  detail_stats: "Detail stats",
}

interface IndicatorVisibilityEditorProps {
  visibility: Record<string, Placement[]>
  onChange: (visibility: Record<string, Placement[]>) => void
}

export function IndicatorVisibilityEditor({ visibility, onChange }: IndicatorVisibilityEditorProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null)

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

  function resetToDefaults(id: string) {
    const desc = INDICATOR_REGISTRY.find((d) => d.id === id)
    if (!desc) return
    const next = { ...visibility }
    delete next[id]
    onChange(next)
  }

  return (
    <div className="space-y-4">
      {CATEGORY_ORDER.filter((cat) => grouped.has(cat)).map((cat) => (
        <div key={cat}>
          <h4 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            {CATEGORY_LABELS[cat]}
          </h4>
          <div className="space-y-1">
            {grouped.get(cat)!.map((desc) => {
              const isExpanded = expandedId === desc.id
              const active = getActivePlacements(desc.id)
              const enabledCount = active.filter((p) => desc.capabilities.includes(p)).length

              return (
                <div key={desc.id} className="rounded-md border">
                  <button
                    type="button"
                    className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-muted/50 transition-colors"
                    onClick={() => setExpandedId(isExpanded ? null : desc.id)}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-medium">{desc.label}</span>
                      <span className="text-xs text-muted-foreground">
                        {enabledCount}/{desc.capabilities.length}
                      </span>
                    </div>
                    <span className="text-xs text-muted-foreground">{isExpanded ? "▾" : "▸"}</span>
                  </button>
                  {isExpanded && (
                    <div className="px-3 pb-3 space-y-2 border-t">
                      <p className="text-xs text-muted-foreground pt-2">{desc.description}</p>
                      <div className="grid grid-cols-1 gap-1.5">
                        {desc.capabilities.map((placement) => (
                          <label
                            key={placement}
                            className="flex items-center justify-between"
                          >
                            <span className="text-sm">{PLACEMENT_LABELS[placement]}</span>
                            <Switch
                              checked={active.includes(placement)}
                              onCheckedChange={(v) => togglePlacement(desc.id, placement, v)}
                            />
                          </label>
                        ))}
                      </div>
                      {desc.id in visibility && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-xs h-7"
                          onClick={() => resetToDefaults(desc.id)}
                        >
                          Reset to defaults
                        </Button>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
