import { useMemo, useCallback } from "react"
import type { Price, Indicator, Annotation } from "@/lib/api"
import { ChartSyncProvider } from "./chart/chart-sync-provider"
import { CandlestickChart } from "./chart/candlestick-chart"
import { SubChart } from "./chart/sub-chart"
import { IndicatorCards } from "./chart/indicator-cards"
import { getSubChartDescriptors, getCardDescriptors, isVisibleAt, type Placement } from "@/lib/indicator-registry"

const SUB_CHART_DESCRIPTORS = getSubChartDescriptors()
const CARD_DESCRIPTORS = getCardDescriptors(true)

interface PriceChartProps {
  prices: Price[]
  indicators: Indicator[]
  annotations: Annotation[]
  /** Placement-based visibility matrix. Missing keys fall back to descriptor defaults. */
  indicatorVisibility?: Record<string, Placement[]>
  /** Indicator IDs to exclude regardless of visibility settings. */
  excludeIndicators?: string[]
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
  excludeIndicators,
  chartType = "candle",
  mainChartHeight = 400,
  currency,
}: PriceChartProps) {
  const isVisible = useCallback(
    (id: string) => {
      if (excludeIndicators?.includes(id)) return false
      return isVisibleAt(indicatorVisibility, id, "detail_chart")
    },
    [indicatorVisibility, excludeIndicators],
  )

  const enabledSubCharts = useMemo(
    () => SUB_CHART_DESCRIPTORS.filter((d) => isVisible(d.id)),
    [isVisible],
  )

  const enabledCards = useMemo(
    () => CARD_DESCRIPTORS.filter((d) => isVisibleAt(indicatorVisibility, d.id, "detail_card")),
    [indicatorVisibility],
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
