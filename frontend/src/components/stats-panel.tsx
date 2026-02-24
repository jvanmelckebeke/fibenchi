import { useMemo } from "react"
import {
  INDICATOR_REGISTRY,
  CATEGORY_ORDER,
  CATEGORY_LABELS,
  isVisibleAt,
  formatIndicatorField,
  getSeriesByField,
  type IndicatorDescriptor,
  type IndicatorCategory,
  type Placement,
} from "@/lib/indicator-registry"
import type { Indicator } from "@/lib/api"

interface StatsPanelProps {
  indicators: Indicator[]
  indicatorVisibility: Record<string, Placement[]>
  currency?: string
}

export function StatsPanel({ indicators, indicatorVisibility, currency }: StatsPanelProps) {
  const latestValues = useMemo(() => {
    if (!indicators.length) return undefined
    return indicators[indicators.length - 1].values
  }, [indicators])

  const grouped = useMemo(() => {
    const visible = INDICATOR_REGISTRY.filter((d) =>
      isVisibleAt(indicatorVisibility, d.id, "detail_stats"),
    )
    const groups = new Map<IndicatorCategory, IndicatorDescriptor[]>()
    for (const desc of visible) {
      const list = groups.get(desc.category) ?? []
      list.push(desc)
      groups.set(desc.category, list)
    }
    return groups
  }, [indicatorVisibility])

  if (!latestValues || grouped.size === 0) return null

  return (
    <div className="rounded-lg border bg-card text-card-foreground divide-y">
      {CATEGORY_ORDER.filter((cat) => grouped.has(cat)).map((cat) => (
        <div key={cat} className="px-4 py-3">
          <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
            {CATEGORY_LABELS[cat]}
          </h3>
          <div className="space-y-2">
            {grouped.get(cat)!.map((desc) => (
              <StatRow
                key={desc.id}
                descriptor={desc}
                values={latestValues}
                currency={currency}
              />
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

function StatRow({
  descriptor,
  values,
  currency,
}: {
  descriptor: IndicatorDescriptor
  values: Record<string, number | string | null>
  currency?: string
}) {
  const mainField = descriptor.series[0]?.field ?? descriptor.fields[0]
  const main = formatIndicatorField(mainField, descriptor, values, currency)
  const secondaryFields = descriptor.fields.filter((f) => f !== mainField)

  // Multi-field indicators: show labeled values
  if (secondaryFields.length > 0) {
    return (
      <div className="space-y-0.5">
        {/* Row 1: label + main value */}
        <div className="flex items-baseline justify-between gap-4">
          <span className="text-sm font-medium">{descriptor.label}</span>
          <span className={`text-sm font-semibold tabular-nums ${main.colorClass}`}>{main.text}</span>
        </div>
        {/* Row 2: description + secondary values */}
        <div className="flex items-baseline justify-between gap-4">
          <p className="text-xs text-muted-foreground">{descriptor.description}</p>
          <div className="flex items-baseline gap-3 tabular-nums shrink-0">
            {secondaryFields.map((f) => {
              const series = getSeriesByField(f)
              const label = series?.label ?? f.replace(/_/g, " ")
              const { text, colorClass } = formatIndicatorField(f, descriptor, values, currency)
              return (
                <span key={f} className="text-xs text-muted-foreground">
                  {label}: <span className={colorClass}>{text}</span>
                </span>
              )
            })}
          </div>
        </div>
      </div>
    )
  }

  // Single-field indicators: simple two-row layout
  return (
    <div className="space-y-0.5">
      <div className="flex items-baseline justify-between gap-4">
        <span className="text-sm font-medium">{descriptor.label}</span>
        <span className={`text-sm font-semibold tabular-nums ${main.colorClass}`}>{main.text}</span>
      </div>
      <p className="text-xs text-muted-foreground">{descriptor.description}</p>
    </div>
  )
}
