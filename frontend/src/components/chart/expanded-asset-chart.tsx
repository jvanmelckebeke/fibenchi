import { useEffect, useState } from "react"
import { Skeleton } from "@/components/ui/skeleton"
import { ChartSyncProvider } from "@/components/chart/chart-sync-provider"
import { CandlestickChart } from "@/components/chart/candlestick-chart"
import { RsiChart } from "@/components/chart/rsi-chart"
import { MacdChart } from "@/components/chart/macd-chart"
import { IndicatorCards } from "@/components/chart/indicator-cards"
import { getCardDescriptors, isVisibleAt } from "@/lib/indicator-registry"
import { useAssetDetail, useAnnotations } from "@/lib/queries"
import { useSettings } from "@/lib/settings"

const CARD_DESCRIPTORS_ALL = getCardDescriptors()
const CARD_DESCRIPTORS_EXCLUSIVE = getCardDescriptors(true)

/** Tailwind `lg` breakpoint (1024px) */
function useIsWide() {
  const [wide, setWide] = useState(() => window.matchMedia("(min-width: 1024px)").matches)
  useEffect(() => {
    const mql = window.matchMedia("(min-width: 1024px)")
    const onChange = () => setWide(mql.matches)
    mql.addEventListener("change", onChange)
    return () => mql.removeEventListener("change", onChange)
  }, [])
  return wide
}

interface ExpandedAssetChartProps {
  symbol: string
  currency?: string
  /**
   * When true, renders a side-by-side layout (chart 80% + indicator cards 20%)
   * suitable for the group table. When false, renders a stacked layout with
   * RSI/MACD sub-charts suitable for the holdings grid.
   */
  compact?: boolean
}

/**
 * Shared expanded-row chart used by both GroupTable and HoldingsGrid.
 * Fetches asset detail for the given symbol and renders candlestick chart
 * with indicator cards.
 */
export function ExpandedAssetChart({ symbol, currency, compact = false }: ExpandedAssetChartProps) {
  const { settings } = useSettings()
  const period = settings.chart_default_period
  const { data: detail, isLoading } = useAssetDetail(symbol, period)
  const prices = detail?.prices
  const indicators = detail?.indicators
  const { data: annotations } = useAnnotations(symbol)
  const isWide = useIsWide()

  const cardDescs = compact ? CARD_DESCRIPTORS_ALL : CARD_DESCRIPTORS_EXCLUSIVE
  const enabledCards = cardDescs.filter(
    (d) => isVisibleAt(settings.indicator_visibility, d.id, "detail_card"),
  )

  const compactChartHeight = isWide ? 300 : 200

  if (isLoading || !prices?.length) {
    if (compact) {
      return (
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="min-w-0 lg:flex-[4]">
            <div className="h-[200px] lg:h-[300px] flex items-center justify-center">
              <Skeleton className="h-full w-full rounded-md" />
            </div>
          </div>
          <div className="flex flex-row flex-wrap lg:flex-col gap-1.5 lg:min-w-[140px] lg:max-w-[200px]">
            {enabledCards.map((d) => (
              <Skeleton key={d.id} className="h-12 w-24 lg:w-full rounded-md" />
            ))}
          </div>
        </div>
      )
    }

    return (
      <div className="space-y-1">
        <Skeleton className="h-[250px] w-full rounded-t-md" />
        <Skeleton className="h-[60px] w-full" />
        <Skeleton className="h-[60px] w-full rounded-b-md" />
      </div>
    )
  }

  if (compact) {
    return (
      <ChartSyncProvider prices={prices} indicators={indicators ?? []}>
        <div className="flex flex-col lg:flex-row gap-4">
          <div className="min-w-0 lg:flex-[4]">
            <CandlestickChart
              annotations={annotations ?? []}
              indicatorVisibility={settings.indicator_visibility}
              excludeIndicators={["rsi", "macd"]}
              chartType={settings.chart_type}
              height={compactChartHeight}
              roundedClass="rounded-md"
            />
          </div>
          <div className="flex flex-row flex-wrap lg:flex-col gap-1.5 lg:min-w-[140px] lg:max-w-[200px] lg:mt-8">
            <IndicatorCards descriptors={enabledCards} currency={currency} compact />
          </div>
        </div>
      </ChartSyncProvider>
    )
  }

  return (
    <ChartSyncProvider prices={prices} indicators={indicators ?? []}>
      <div className="space-y-0">
        <CandlestickChart
          annotations={annotations ?? []}
          indicatorVisibility={settings.indicator_visibility}
          excludeIndicators={["rsi", "macd"]}
          chartType={settings.chart_type}
          height={250}
          hideTimeAxis
          showLegend
          roundedClass="rounded-t-md"
        />
        <RsiChart showLegend roundedClass="" />
        <MacdChart showLegend roundedClass="rounded-b-md" />
        <IndicatorCards descriptors={enabledCards} currency={currency} compact />
      </div>
    </ChartSyncProvider>
  )
}
