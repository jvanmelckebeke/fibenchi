import { useMemo, useCallback } from "react"
import type { Price, Indicator, Annotation } from "@/lib/api"
import { ChartSyncProvider } from "./chart/chart-sync-provider"
import { CandlestickChart } from "./chart/candlestick-chart"
import { SubChart } from "./chart/sub-chart"
import { IndicatorCards } from "./chart/indicator-cards"
import { getSubChartDescriptors, getCardDescriptors } from "@/lib/indicator-registry"

const SUB_CHART_DESCRIPTORS = getSubChartDescriptors()
const CARD_DESCRIPTORS = getCardDescriptors()

interface PriceChartProps {
  prices: Price[]
  indicators: Indicator[]
  annotations: Annotation[]
  /** Per-descriptor visibility (keys = descriptor IDs). Missing keys default to true. */
  indicatorVisibility?: Record<string, boolean>
  chartType?: "candle" | "line"
  mainChartHeight?: number
  /** ISO 4217 currency code for formatting price-denominated indicators (e.g. ATR). */
  currency?: string
}

export function PriceChart({
  prices,
  indicators,
  annotations,
  indicatorVisibility,
  chartType = "candle",
  mainChartHeight = 400,
  currency,
}: PriceChartProps) {
  const isVisible = useCallback(
    (id: string) => indicatorVisibility?.[id] !== false,
    [indicatorVisibility],
  )

  const enabledSubCharts = useMemo(
    () => SUB_CHART_DESCRIPTORS.filter((d) => isVisible(d.id)),
    [isVisible],
  )

  const enabledCards = useMemo(
    () => CARD_DESCRIPTORS.filter((d) => isVisible(d.id)),
    [isVisible],
  )

  const hasSubCharts = enabledSubCharts.length > 0
  const mainRoundedClass = hasSubCharts ? "rounded-t-md" : "rounded-md"

  return (
    <ChartSyncProvider prices={prices} indicators={indicators}>
      <div className="mb-4">
        <CandlestickChart
          annotations={annotations}
          indicatorVisibility={indicatorVisibility}
          chartType={chartType}
          height={mainChartHeight}
          hideTimeAxis={hasSubCharts}
          roundedClass={mainRoundedClass}
        />
        {enabledSubCharts.map((desc, idx) => (
          <SubChart
            key={desc.id}
            descriptorId={desc.id}
            roundedClass={idx === enabledSubCharts.length - 1 ? "rounded-b-md" : ""}
          />
        ))}
        <IndicatorCards descriptors={enabledCards} currency={currency} />
      </div>
    </ChartSyncProvider>
  )
}
