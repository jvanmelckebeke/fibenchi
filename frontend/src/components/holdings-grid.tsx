import { useState } from "react"
import { Link } from "react-router-dom"
import { ChevronRight, ChevronDown, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { IndicatorCell } from "@/components/indicator-cell"
import { ChartSyncProvider } from "@/components/chart/chart-sync-provider"
import { CandlestickChart } from "@/components/chart/candlestick-chart"
import { RsiChart } from "@/components/chart/rsi-chart"
import { MacdChart } from "@/components/chart/macd-chart"
import { formatPrice, formatChangePct } from "@/lib/format"
import { getNumericValue, getStringValue, getHoldingSummaryDescriptors } from "@/lib/indicator-registry"
import { useAssetDetail, useAnnotations } from "@/lib/queries"
import { useSettings } from "@/lib/settings"

export interface IndicatorData {
  currency: string
  close: number | null
  change_pct: number | null
  values: Record<string, number | string | null>
}

export interface HoldingsGridRow {
  key: string | number
  symbol: string
  name: string
  percent: number | null
}

interface HoldingsGridProps {
  rows: HoldingsGridRow[]
  indicatorMap: ReadonlyMap<string, IndicatorData>
  indicatorsLoading: boolean
  onRemove?: (key: string | number) => void
  linkTarget?: "_blank"
}

const SUMMARY_DESCRIPTORS = getHoldingSummaryDescriptors()

export function HoldingsGrid({ rows, indicatorMap, indicatorsLoading, onRemove, linkTarget }: HoldingsGridProps) {
  const [expandedKeys, setExpandedKeys] = useState<Set<string | number>>(new Set())
  const hasRemove = !!onRemove

  const toggleExpand = (key: string | number) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })
  }

  // base columns: chevron + symbol + name + % + price + chg% + indicator summary columns + optional remove
  const totalColSpan = 1 + 1 + 1 + 1 + 1 + 1 + SUMMARY_DESCRIPTORS.length + (hasRemove ? 1 : 0)

  return (
    <div className="overflow-x-auto">
      <div className={hasRemove ? "min-w-[750px]" : "min-w-[700px]"}>
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="w-6" />
              <th className="text-left text-xs font-medium text-muted-foreground px-2 py-1">Symbol</th>
              <th className="text-left text-xs font-medium text-muted-foreground px-2 py-1">Name</th>
              <th className="text-right text-xs font-medium text-muted-foreground px-2 py-1">%</th>
              <th className="text-right text-xs font-medium text-muted-foreground px-2 py-1">Price</th>
              <th className="text-right text-xs font-medium text-muted-foreground px-2 py-1">Chg%</th>
              {SUMMARY_DESCRIPTORS.map((desc) => (
                <th key={desc.id} className="text-right text-xs font-medium text-muted-foreground px-2 py-1">
                  {desc.holdingSummary!.label}
                </th>
              ))}
              {hasRemove && <th className="w-8" />}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <HoldingRow
                key={row.key}
                row={row}
                indicator={indicatorMap.get(row.symbol)}
                indicatorsLoading={indicatorsLoading}
                expanded={expandedKeys.has(row.key)}
                onToggle={() => toggleExpand(row.key)}
                onRemove={onRemove ? () => onRemove(row.key) : undefined}
                linkTarget={linkTarget}
                totalColSpan={totalColSpan}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function HoldingRow({
  row,
  indicator,
  indicatorsLoading,
  expanded,
  onToggle,
  onRemove,
  linkTarget,
  totalColSpan,
}: {
  row: HoldingsGridRow
  indicator: IndicatorData | undefined
  indicatorsLoading: boolean
  expanded: boolean
  onToggle: () => void
  onRemove?: () => void
  linkTarget?: "_blank"
  totalColSpan: number
}) {
  const chg = formatChangePct(indicator?.change_pct ?? null)

  return (
    <>
      <tr
        className="border-b border-border hover:bg-muted/30 cursor-pointer group/row transition-colors"
        onClick={onToggle}
      >
        <td className="py-1 pl-2">
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
        <td className="py-1 px-2">
          <Link
            to={`/asset/${row.symbol}`}
            {...(linkTarget === "_blank" ? { target: "_blank", rel: "noopener noreferrer" } : {})}
            className="font-mono text-xs text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {row.symbol}
          </Link>
        </td>
        <td className="py-1 px-2 text-muted-foreground truncate text-xs max-w-[200px]">
          {row.name}
        </td>
        <td className="py-1 px-2 text-right text-xs">
          {row.percent != null ? `${row.percent.toFixed(1)}%` : "\u2014"}
        </td>
        {indicatorsLoading ? (
          <td
            colSpan={2 + SUMMARY_DESCRIPTORS.length}
            className="py-1 px-2 text-right text-xs text-muted-foreground animate-pulse"
          >
            Loading...
          </td>
        ) : (
          <>
            <td className="py-1 px-2 text-right text-xs">
              {indicator?.close != null ? formatPrice(indicator.close, indicator.currency, 0) : "\u2014"}
            </td>
            <td className={`py-1 px-2 text-right text-xs ${chg.className}`}>
              {chg.text ?? "\u2014"}
            </td>
            {SUMMARY_DESCRIPTORS.map((desc) => {
              const hs = desc.holdingSummary!
              return (
                <td key={desc.id} className="py-1 px-2 text-right">
                  <HoldingSummaryCell
                    format={hs.format}
                    field={hs.field}
                    colorMap={hs.colorMap}
                    values={indicator?.values}
                    close={indicator?.close ?? null}
                  />
                </td>
              )
            })}
          </>
        )}
        {onRemove && (
          <td className="py-1 pr-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-5 w-5 opacity-0 group-hover/row:opacity-100 transition-opacity"
              onClick={(e) => {
                e.stopPropagation()
                onRemove()
              }}
            >
              <X className="h-3 w-3" />
            </Button>
          </td>
        )}
      </tr>
      {expanded && (
        <tr>
          <td colSpan={totalColSpan} className="bg-muted/20 p-4 border-b border-border">
            <ExpandedHoldingContent symbol={row.symbol} />
          </td>
        </tr>
      )}
    </>
  )
}

function ExpandedHoldingContent({ symbol }: { symbol: string }) {
  const { settings } = useSettings()
  const period = settings.chart_default_period
  const { data: detail, isLoading } = useAssetDetail(symbol, period)
  const prices = detail?.prices
  const indicators = detail?.indicators
  const { data: annotations } = useAnnotations(symbol)

  if (isLoading || !prices?.length) {
    return (
      <div className="space-y-1">
        <Skeleton className="h-[250px] w-full rounded-t-md" />
        <Skeleton className="h-[60px] w-full" />
        <Skeleton className="h-[60px] w-full rounded-b-md" />
      </div>
    )
  }

  return (
    <ChartSyncProvider prices={prices} indicators={indicators ?? []}>
      <div className="space-y-0">
        <CandlestickChart
          annotations={annotations ?? []}
          indicatorVisibility={{
            ...settings.detail_indicator_visibility,
            rsi: false,
            macd: false,
          }}
          chartType={settings.chart_type}
          height={250}
          hideTimeAxis
          showLegend
          roundedClass="rounded-t-md"
        />
        <RsiChart showLegend roundedClass="" />
        <MacdChart showLegend roundedClass="rounded-b-md" />
      </div>
    </ChartSyncProvider>
  )
}

function HoldingSummaryCell({
  format,
  field,
  colorMap,
  values,
  close,
}: {
  format: "numeric" | "compare_close" | "string_map"
  field: string
  colorMap?: Record<string, string>
  values?: Record<string, number | string | null>
  close: number | null
}) {
  if (format === "numeric") {
    const val = getNumericValue(values, field)
    return <IndicatorCell value={val != null ? val.toFixed(0) : null} />
  }

  if (format === "compare_close") {
    const val = getNumericValue(values, field)
    const above = val != null && close != null ? close > val : null
    return (
      <IndicatorCell
        value={above !== null ? (above ? "Above" : "Below") : null}
        className={above === true ? "text-emerald-500" : above === false ? "text-red-500" : ""}
      />
    )
  }

  // string_map
  const str = getStringValue(values, field)
  const colorClass = str != null && colorMap ? (colorMap[str] ?? "") : ""
  const display = str != null ? str.charAt(0).toUpperCase() + str.slice(1) : null
  return <IndicatorCell value={display} className={colorClass} />
}
