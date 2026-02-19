import { Skeleton } from "@/components/ui/skeleton"
import { ChartSyncProvider } from "@/components/chart/chart-sync-provider"
import { CandlestickChart } from "@/components/chart/candlestick-chart"
import { RsiChart } from "@/components/chart/rsi-chart"
import { MacdChart } from "@/components/chart/macd-chart"
import { IndicatorCards } from "@/components/chart/indicator-cards"
import { getCardDescriptors, isIndicatorVisible } from "@/lib/indicator-registry"
import { useAssetDetail, useAnnotations } from "@/lib/queries"
import { useSettings } from "@/lib/settings"

const CARD_DESCRIPTORS_ALL = getCardDescriptors()
const CARD_DESCRIPTORS_EXCLUSIVE = getCardDescriptors(true)

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

  const cardDescs = compact ? CARD_DESCRIPTORS_ALL : CARD_DESCRIPTORS_EXCLUSIVE
  const enabledCards = cardDescs.filter(
    (d) => isIndicatorVisible(settings.detail_indicator_visibility, d.id),
  )

  if (isLoading || !prices?.length) {
    if (compact) {
      return (
        <div className="flex gap-4">
          <div className="flex-[4] min-w-0">
            <div className="h-[300px] flex items-center justify-center">
              <Skeleton className="h-full w-full rounded-md" />
            </div>
          </div>
          <div className="flex-1 flex flex-col gap-1.5 min-w-[140px] max-w-[200px]">
            {enabledCards.map((d) => (
              <Skeleton key={d.id} className="h-12 w-full rounded-md" />
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
        <div className="flex gap-4">
          <div className="flex-[4] min-w-0">
            <CandlestickChart
              annotations={annotations ?? []}
              indicatorVisibility={{
                ...settings.detail_indicator_visibility,
                rsi: false,
                macd: false,
              }}
              chartType={settings.chart_type}
              height={300}
              roundedClass="rounded-md"
            />
          </div>
          <div className="flex-1 min-w-[140px] max-w-[200px] mt-8">
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
        <IndicatorCards descriptors={enabledCards} currency={currency} compact />
      </div>
    </ChartSyncProvider>
  )
}
