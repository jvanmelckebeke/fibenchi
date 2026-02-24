import { useMemo } from "react"
import {
  INDICATOR_REGISTRY,
  isVisibleAt,
  getNumericValue,
  resolveThresholdColor,
  resolveAdxColor,
  type IndicatorDescriptor,
  type IndicatorCategory,
  type Placement,
} from "@/lib/indicator-registry"
import { currencySymbol, formatCompactNumber } from "@/lib/format"
import type { Indicator } from "@/lib/api"

const CATEGORY_ORDER: IndicatorCategory[] = ["fundamentals", "market_data", "technical", "volatility"]
const CATEGORY_LABELS: Record<IndicatorCategory, string> = {
  fundamentals: "Fundamentals",
  market_data: "Market Data",
  technical: "Technical",
  volatility: "Volatility",
}

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
          <div className="space-y-1.5">
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
  const mainVal = getNumericValue(values, mainField)

  let formatted: string
  let colorClass = ""

  if (mainVal == null) {
    formatted = "--"
    colorClass = "text-muted-foreground"
  } else {
    if (descriptor.compactFormat) {
      formatted = formatCompactNumber(mainVal)
    } else {
      const prefix = currency && descriptor.priceDenominated ? currencySymbol(currency) : ""
      formatted = `${prefix}${mainVal.toFixed(descriptor.decimals)}${descriptor.suffix ?? ""}`
    }
    colorClass =
      descriptor.id === "adx"
        ? resolveAdxColor(mainVal, values)
        : resolveThresholdColor(descriptor.series[0]?.thresholdColors, mainVal) || "text-foreground"
  }

  // For multi-field indicators, show secondary values
  const secondaryFields = descriptor.fields.slice(1).filter((f) => f !== mainField)

  return (
    <div className="flex items-baseline justify-between gap-4">
      <div className="flex-1 min-w-0">
        <span className="text-sm font-medium">{descriptor.label}</span>
        <span className="text-xs text-muted-foreground ml-2">{descriptor.description}</span>
      </div>
      <div className="flex items-baseline gap-3 tabular-nums shrink-0">
        {secondaryFields.map((f) => {
          const v = getNumericValue(values, f)
          return (
            <span key={f} className="text-xs text-muted-foreground">
              {v != null ? (descriptor.compactFormat ? formatCompactNumber(v) : v.toFixed(descriptor.decimals)) : "--"}
            </span>
          )
        })}
        <span className={`text-sm font-semibold ${colorClass}`}>{formatted}</span>
      </div>
    </div>
  )
}
