import { PriceChart } from "@/components/price-chart"
import { ChartSkeleton } from "@/components/chart-skeleton"
import { IntradayChart } from "@/components/intraday-chart"
import { useAssetDetail, useAnnotations } from "@/lib/queries"
import { useIntraday, useQuote } from "@/lib/quote-stream"
import type { Placement } from "@/lib/indicator-registry"
import type { ChartMode } from "./header"

export function ChartSection({
  symbol,
  period,
  indicatorVisibility,
  chartType,
  currency,
  mode,
}: {
  symbol: string
  period: string
  indicatorVisibility: Record<string, Placement[]>
  chartType: "candle" | "line"
  currency?: string
  mode: ChartMode
}) {
  if (mode === "live") {
    return <LiveChartSection symbol={symbol} />
  }
  return (
    <HistoricalChartSection
      symbol={symbol}
      period={period}
      indicatorVisibility={indicatorVisibility}
      chartType={chartType}
      currency={currency}
    />
  )
}

function LiveChartSection({ symbol }: { symbol: string }) {
  const intraday = useIntraday()
  const upperSymbol = symbol.toUpperCase()
  const points = intraday[upperSymbol]
  const quote = useQuote(upperSymbol)
  const previousClose = quote?.previous_close ?? null

  if (!points || points.length === 0) {
    return <ChartSkeleton height={520} />
  }

  return (
    <div className="h-[520px] rounded-md border border-border/50 overflow-hidden">
      <IntradayChart
        points={points}
        previousClose={previousClose}
        interactive
      />
    </div>
  )
}

function HistoricalChartSection({
  symbol,
  period,
  indicatorVisibility,
  chartType,
  currency,
}: {
  symbol: string
  period: string
  indicatorVisibility: Record<string, Placement[]>
  chartType: "candle" | "line"
  currency?: string
}) {
  const { data: detail, isLoading: detailLoading, isFetching: detailFetching } = useAssetDetail(symbol, period)
  const prices = detail?.prices
  const indicators = detail?.indicators
  const { data: annotations } = useAnnotations(symbol)

  if (detailLoading) {
    return <ChartSkeleton height={520} />
  }

  if (!prices?.length) {
    return (
      <div className="h-[520px] flex items-center justify-center text-muted-foreground">
        No price data. Click Refresh to fetch.
      </div>
    )
  }

  return (
    <div className="relative">
      {detailFetching && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-primary/20 overflow-hidden z-10 rounded-t-md">
          <div className="h-full w-1/3 bg-primary animate-[slide_1s_ease-in-out_infinite]" />
        </div>
      )}
      <PriceChart
        prices={prices}
        indicators={indicators ?? []}
        annotations={annotations ?? []}
        indicatorVisibility={indicatorVisibility}
        chartType={chartType}
        currency={currency}
      />
    </div>
  )
}
