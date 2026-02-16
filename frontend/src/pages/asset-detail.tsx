import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, ExternalLink, Loader2, RefreshCw, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { PriceChart } from "@/components/price-chart"
import { ChartSkeleton } from "@/components/chart-skeleton"
import { ConnectedThesis } from "@/components/connected-thesis"
import { ConnectedAnnotations } from "@/components/connected-annotations"
import { TagInput } from "@/components/tag-input"
import { PeriodSelector } from "@/components/period-selector"
import { HoldingsGrid, type HoldingsGridRow } from "@/components/holdings-grid"
import { buildYahooFinanceUrl, formatPrice } from "@/lib/format"
import { useQuotes } from "@/lib/quote-stream"
import { usePriceFlash } from "@/lib/use-price-flash"
import type { EtfHoldings } from "@/lib/api"
import {
  useAssets,
  useCreateAsset,
  usePrices,
  useIndicators,
  useRefreshPrices,
  useEtfHoldings,
  useHoldingsIndicators,
  useAnnotations,
  useCreateAnnotation,
  useDeleteAnnotation,
  useThesis,
  useUpdateThesis,
} from "@/lib/queries"
import { useSettings } from "@/lib/settings"


export function AssetDetailPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const { settings } = useSettings()
  const [period, setPeriod] = useState<string>(settings.chart_default_period)
  const { data: assets } = useAssets()
  const asset = assets?.find((a) => a.symbol === symbol?.toUpperCase())
  const isWatchlisted = !!asset
  const isEtf = asset?.type === "etf"

  if (!symbol) return null

  return (
    <div className="p-6 space-y-6">
      <Header symbol={symbol} name={asset?.name} currency={asset?.currency ?? "USD"} period={period} setPeriod={setPeriod} isWatchlisted={isWatchlisted} />
      <ChartSection
        symbol={symbol}
        period={period}
        showSma20={settings.detail_show_sma20}
        showSma50={settings.detail_show_sma50}
        showBollinger={settings.detail_show_bollinger}
        showRsiChart={settings.detail_show_rsi_chart}
        showMacdChart={settings.detail_show_macd_chart}
        chartType={settings.chart_type}
      />
      {isEtf && <HoldingsSection symbol={symbol} />}
      {isWatchlisted && (
        <>
          <TagInput symbol={symbol} currentTags={asset?.tags ?? []} />
          <ConnectedAnnotations
            useAnnotationsQuery={() => useAnnotations(symbol)}
            useCreateMutation={() => useCreateAnnotation(symbol)}
            useDeleteMutation={() => useDeleteAnnotation(symbol)}
          />
          <ConnectedThesis
            useThesisQuery={() => useThesis(symbol)}
            useUpdateMutation={() => useUpdateThesis(symbol)}
          />
        </>
      )}
    </div>
  )
}

function Header({
  symbol,
  name,
  currency,
  period,
  setPeriod,
  isWatchlisted,
}: {
  symbol: string
  name?: string
  currency: string
  period: string
  setPeriod: (p: string) => void
  isWatchlisted: boolean
}) {
  const refresh = useRefreshPrices(symbol)
  const createAsset = useCreateAsset()
  const quotes = useQuotes()
  const quote = quotes[symbol.toUpperCase()]
  const price = quote?.price ?? null
  const changePct = quote?.change_percent ?? null
  const [priceRef, pctRef] = usePriceFlash(price)

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <Link to="/">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">{symbol}</h1>
          {name && <p className="text-sm text-muted-foreground">{name}</p>}
        </div>
        {price != null && (
          <span ref={priceRef} className="text-xl font-semibold tabular-nums rounded px-1">
            {formatPrice(price, currency)}
          </span>
        )}
        {changePct != null && (
          <span
            ref={pctRef}
            className={`text-sm font-medium tabular-nums rounded px-1 ${
              changePct >= 0 ? "text-green-500" : "text-red-500"
            }`}
          >
            {changePct >= 0 ? "+" : ""}
            {changePct.toFixed(2)}%
          </span>
        )}
        <a
          href={buildYahooFinanceUrl(symbol)}
          target="_blank"
          rel="noopener noreferrer"
          title="View on Yahoo Finance"
        >
          <Button variant="ghost" size="icon" className="h-8 w-8">
            <ExternalLink className="h-4 w-4 text-muted-foreground" />
          </Button>
        </a>
        {!isWatchlisted && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => createAsset.mutate({ symbol: symbol.toUpperCase(), watchlisted: true })}
            disabled={createAsset.isPending}
          >
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            {createAsset.isPending ? "Adding..." : "Add to Watchlist"}
          </Button>
        )}
      </div>
      <div className="flex items-center gap-2">
        <PeriodSelector value={period} onChange={setPeriod} />
        {isWatchlisted && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => refresh.mutate(period)}
            disabled={refresh.isPending}
          >
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refresh.isPending ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        )}
      </div>
    </div>
  )
}

function ChartSection({
  symbol,
  period,
  showSma20,
  showSma50,
  showBollinger,
  showRsiChart,
  showMacdChart,
  chartType,
}: {
  symbol: string
  period: string
  showSma20: boolean
  showSma50: boolean
  showBollinger: boolean
  showRsiChart: boolean
  showMacdChart: boolean
  chartType: "candle" | "line"
}) {
  const { data: prices, isLoading: pricesLoading, isFetching: pricesFetching } = usePrices(symbol, period)
  const { data: indicators, isLoading: indicatorsLoading, isFetching: indicatorsFetching } = useIndicators(symbol, period)
  const { data: annotations } = useAnnotations(symbol)

  if (pricesLoading || indicatorsLoading) {
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
      {(pricesFetching || indicatorsFetching) && (
        <div className="absolute top-0 left-0 right-0 h-0.5 bg-primary/20 overflow-hidden z-10 rounded-t-md">
          <div className="h-full w-1/3 bg-primary animate-[slide_1s_ease-in-out_infinite]" />
        </div>
      )}
      <PriceChart
        prices={prices}
        indicators={indicators ?? []}
        annotations={annotations ?? []}
        showSma20={showSma20}
        showSma50={showSma50}
        showBollinger={showBollinger}
        showRsiChart={showRsiChart}
        showMacdChart={showMacdChart}
        chartType={chartType}
      />
    </div>
  )
}


function HoldingsSection({ symbol }: { symbol: string }) {
  const { data, isLoading } = useEtfHoldings(symbol, true)
  const { data: indicators, isLoading: indicatorsLoading } = useHoldingsIndicators(symbol, !!data?.top_holdings.length)

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-4">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Loading holdings...</span>
      </div>
    )
  }
  if (!data || (!data.top_holdings.length && !data.sector_weightings.length)) {
    return null
  }

  const indicatorMap = new Map((indicators ?? []).map((i) => [i.symbol, i]))

  return (
    <div className="space-y-6">
      <TopHoldingsCard data={data} indicatorMap={indicatorMap} indicatorsLoading={indicatorsLoading} />
      <SectorWeightingsCard data={data} />
    </div>
  )
}

function TopHoldingsCard({
  data,
  indicatorMap,
  indicatorsLoading,
}: {
  data: EtfHoldings
  indicatorMap: ReadonlyMap<string, { currency: string; close: number | null; change_pct: number | null; rsi: number | null; sma_20: number | null; macd: number | null; macd_signal: number | null; macd_hist: number | null; macd_signal_dir: string | null; bb_upper: number | null; bb_middle: number | null; bb_lower: number | null; bb_position: string | null }>
  indicatorsLoading: boolean
}) {
  const rows: HoldingsGridRow[] = data.top_holdings.map((h) => ({
    key: h.symbol,
    symbol: h.symbol,
    name: h.name,
    percent: h.percent,
  }))

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">
        Top {data.top_holdings.length} Holdings ({data.total_percent}% of Total Assets)
      </h3>
      <HoldingsGrid
        rows={rows}
        indicatorMap={indicatorMap}
        indicatorsLoading={indicatorsLoading}
        linkTarget="_blank"
      />
    </Card>
  )
}

function SectorWeightingsCard({ data }: { data: EtfHoldings }) {
  if (!data.sector_weightings.length) return null
  const maxPct = Math.max(...data.sector_weightings.map((s) => s.percent))

  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">Sector Weightings</h3>
      <div className="space-y-0">
        <div className="grid grid-cols-[1fr_6rem_3.5rem] text-xs text-muted-foreground border-b border-border pb-1 mb-1">
          <span>Sector</span>
          <span></span>
          <span className="text-right">Weight</span>
        </div>
        {data.sector_weightings.map((s) => (
          <div key={s.sector} className="grid grid-cols-[1fr_6rem_3.5rem] text-sm py-1 items-center">
            <span className="text-xs">{s.sector}</span>
            <div className="h-3 bg-muted rounded overflow-hidden">
              <div
                className="h-full bg-amber-500 rounded"
                style={{ width: `${(s.percent / maxPct) * 100}%` }}
              />
            </div>
            <span className="text-right font-medium text-xs">{s.percent.toFixed(2)}%</span>
          </div>
        ))}
      </div>
    </Card>
  )
}
