import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, ExternalLink, RefreshCw, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { PriceChart } from "@/components/price-chart"
import { ChartSkeleton } from "@/components/chart-skeleton"
import { ThesisEditor } from "@/components/thesis-editor"
import { AnnotationsList } from "@/components/annotations-list"
import { TagInput } from "@/components/tag-input"
import { PeriodSelector } from "@/components/period-selector"
import { HoldingsGrid, type HoldingsGridRow } from "@/components/holdings-grid"
import { MarketStatusDot } from "@/components/market-status-dot"
import { buildYahooFinanceUrl, formatPrice, formatChangePct } from "@/lib/format"
import { useQuotes } from "@/lib/quote-stream"
import { usePriceFlash } from "@/lib/use-price-flash"
import type { EtfHoldings } from "@/lib/api"
import {
  useAssets,
  useCreateAsset,
  useAssetDetail,
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
  const isTracked = !!asset
  const isEtf = asset?.type === "etf"

  if (!symbol) return null

  return (
    <div className="p-6 space-y-6">
      <Header symbol={symbol} name={asset?.name} currency={asset?.currency ?? "USD"} period={period} setPeriod={setPeriod} isTracked={isTracked} />
      <ChartSection
        symbol={symbol}
        period={period}
        indicatorVisibility={settings.detail_indicator_visibility}
        chartType={settings.chart_type}
        currency={asset?.currency}
      />
      {isEtf && <HoldingsSection symbol={symbol} />}
      {isTracked && (
        <>
          <TagInput symbol={symbol} currentTags={asset?.tags ?? []} />
          <AssetAnnotations symbol={symbol} />
          <AssetThesis symbol={symbol} />
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
  isTracked,
}: {
  symbol: string
  name?: string
  currency: string
  period: string
  setPeriod: (p: string) => void
  isTracked: boolean
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
          <div className="flex items-center gap-2">
            <MarketStatusDot marketState={quote?.market_state} className="h-2.5 w-2.5" />
            <h1 className="text-2xl font-bold">{symbol}</h1>
          </div>
          {name && <p className="text-sm text-muted-foreground">{name}</p>}
        </div>
        {price != null && (
          <span ref={priceRef} className="text-xl font-semibold tabular-nums rounded px-1">
            {formatPrice(price, currency)}
          </span>
        )}
        {changePct != null && (() => {
          const chg = formatChangePct(changePct)
          return (
            <span
              ref={pctRef}
              className={`text-sm font-medium tabular-nums rounded px-1 ${chg.className}`}
            >
              {chg.text}
            </span>
          )
        })()}
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
        {!isTracked && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => createAsset.mutate({ symbol: symbol.toUpperCase() })}
            disabled={createAsset.isPending}
          >
            <Plus className="h-3.5 w-3.5 mr-1.5" />
            {createAsset.isPending ? "Adding..." : "Track"}
          </Button>
        )}
      </div>
      <div className="flex items-center gap-2">
        <PeriodSelector value={period} onChange={setPeriod} />
        {isTracked && (
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
  indicatorVisibility,
  chartType,
  currency,
}: {
  symbol: string
  period: string
  indicatorVisibility: Record<string, boolean>
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


function HoldingsSection({ symbol }: { symbol: string }) {
  const { data, isLoading } = useEtfHoldings(symbol, true)
  const { data: indicators, isLoading: indicatorsLoading } = useHoldingsIndicators(symbol, !!data?.top_holdings.length)

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Card className="p-4">
          <Skeleton className="h-4 w-48 mb-3" />
          <div className="space-y-2">
            {Array.from({ length: 8 }, (_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-4 w-14" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-4 w-10" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-12" />
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-4">
          <Skeleton className="h-4 w-36 mb-3" />
          <div className="space-y-2">
            {Array.from({ length: 6 }, (_, i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-3 rounded" style={{ width: `${80 - i * 10}%` }} />
                <Skeleton className="h-4 w-12" />
              </div>
            ))}
          </div>
        </Card>
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
  indicatorMap: ReadonlyMap<string, { currency: string; close: number | null; change_pct: number | null; values: Record<string, number | string | null> }>
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

function AssetAnnotations({ symbol }: { symbol: string }) {
  const { data: annotations } = useAnnotations(symbol)
  const createAnnotation = useCreateAnnotation(symbol)
  const deleteAnnotation = useDeleteAnnotation(symbol)

  return (
    <AnnotationsList
      annotations={annotations}
      onCreate={(data) => createAnnotation.mutate(data)}
      onDelete={(id) => deleteAnnotation.mutate(id)}
      isCreating={createAnnotation.isPending}
    />
  )
}

function AssetThesis({ symbol }: { symbol: string }) {
  const { data: thesis } = useThesis(symbol)
  const updateThesis = useUpdateThesis(symbol)

  return (
    <ThesisEditor
      thesis={thesis}
      onSave={(content) => updateThesis.mutate(content)}
      isSaving={updateThesis.isPending}
    />
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
