import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, ExternalLink, Loader2, RefreshCw, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { PriceChart } from "@/components/price-chart"
import { ThesisEditor } from "@/components/thesis-editor"
import { AnnotationsList } from "@/components/annotations-list"
import { TagInput } from "@/components/tag-input"
import { formatPrice, buildYahooFinanceUrl } from "@/lib/format"
import type { EtfHoldings, HoldingIndicator } from "@/lib/api"
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

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"] as const

export function AssetDetailPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const [period, setPeriod] = useState<string>("1y")
  const { data: assets } = useAssets()
  const asset = assets?.find((a) => a.symbol === symbol?.toUpperCase())
  const isWatchlisted = !!asset
  const isEtf = asset?.type === "etf"

  if (!symbol) return null

  return (
    <div className="p-6 space-y-6">
      <Header symbol={symbol} period={period} setPeriod={setPeriod} isWatchlisted={isWatchlisted} />
      <ChartSection symbol={symbol} period={period} />
      {isEtf && <HoldingsSection symbol={symbol} />}
      {isWatchlisted && (
        <>
          <TagInput symbol={symbol} currentTags={asset?.tags ?? []} />
          <AnnotationsSection symbol={symbol} />
          <ThesisSection symbol={symbol} />
        </>
      )}
    </div>
  )
}

function Header({
  symbol,
  period,
  setPeriod,
  isWatchlisted,
}: {
  symbol: string
  period: string
  setPeriod: (p: string) => void
  isWatchlisted: boolean
}) {
  const refresh = useRefreshPrices(symbol)
  const createAsset = useCreateAsset()

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <Link to="/">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <h1 className="text-2xl font-bold">{symbol}</h1>
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
        <div className="flex gap-1">
          {PERIODS.map((p) => (
            <Button
              key={p}
              variant={period === p ? "default" : "ghost"}
              size="sm"
              onClick={() => setPeriod(p)}
              className="text-xs"
            >
              {p}
            </Button>
          ))}
        </div>
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

function ChartSection({ symbol, period }: { symbol: string; period: string }) {
  const { data: prices, isLoading: pricesLoading } = usePrices(symbol, period)
  const { data: indicators, isLoading: indicatorsLoading } = useIndicators(symbol, period)
  const { data: annotations } = useAnnotations(symbol)

  if (pricesLoading || indicatorsLoading) {
    return (
      <div className="h-[520px] flex flex-col items-center justify-center gap-2 text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="text-sm">Loading chart...</span>
      </div>
    )
  }

  if (!prices?.length) {
    return (
      <div className="h-[520px] flex items-center justify-center text-muted-foreground">
        No price data. Click Refresh to fetch.
      </div>
    )
  }

  return <PriceChart prices={prices} indicators={indicators ?? []} annotations={annotations ?? []} />
}

function ThesisSection({ symbol }: { symbol: string }) {
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

function AnnotationsSection({ symbol }: { symbol: string }) {
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

function IndicatorCell({ value, className = "" }: { value: string | null; className?: string }) {
  return (
    <span className={`text-right text-xs ${value === null ? "text-muted-foreground" : className}`}>
      {value ?? "—"}
    </span>
  )
}

function formatChangePct(v: number | null): { text: string | null; className: string } {
  if (v === null) return { text: null, className: "" }
  const sign = v >= 0 ? "+" : ""
  return {
    text: `${sign}${v.toFixed(2)}%`,
    className: v >= 0 ? "text-emerald-500" : "text-red-500",
  }
}

function TopHoldingsCard({
  data,
  indicatorMap,
  indicatorsLoading,
}: {
  data: EtfHoldings
  indicatorMap: Map<string, HoldingIndicator>
  indicatorsLoading: boolean
}) {
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">
        Top {data.top_holdings.length} Holdings ({data.total_percent}% of Total Assets)
      </h3>
      <div className="overflow-x-auto">
        <div className="min-w-[700px] space-y-0">
          <div className="grid grid-cols-[4rem_1fr_3.5rem_5rem_4rem_3.5rem_3.5rem_4rem_3.5rem] text-xs text-muted-foreground border-b border-border pb-1 mb-1 gap-x-2">
            <span>Symbol</span>
            <span>Company</span>
            <span className="text-right">%</span>
            <span className="text-right">Price</span>
            <span className="text-right">Chg%</span>
            <span className="text-right">RSI</span>
            <span className="text-right">SMA20</span>
            <span className="text-right">MACD</span>
            <span className="text-right">BB</span>
          </div>
          {data.top_holdings.map((h) => {
            const ind = indicatorMap.get(h.symbol)
            const chg = formatChangePct(ind?.change_pct ?? null)
            const rsiVal = ind?.rsi
            const rsiColor = rsiVal != null ? (rsiVal > 70 ? "text-red-500" : rsiVal < 30 ? "text-emerald-500" : "") : ""
            const smaAbove = ind?.sma_20 != null && ind?.close != null ? ind.close > ind.sma_20 : null
            const macdDir = ind?.macd_signal_dir
            const bbPos = ind?.bb_position

            return (
              <div key={h.symbol} className="grid grid-cols-[4rem_1fr_3.5rem_5rem_4rem_3.5rem_3.5rem_4rem_3.5rem] text-sm py-1 hover:bg-muted/50 rounded gap-x-2 items-center">
                <a href={`/asset/${h.symbol}`} target="_blank" rel="noopener noreferrer" className="font-mono text-xs text-primary hover:underline">{h.symbol}</a>
                <span className="text-muted-foreground truncate text-xs">{h.name}</span>
                <span className="text-right font-medium text-xs">{h.percent.toFixed(1)}%</span>
                {indicatorsLoading ? (
                  <span className="col-span-6 text-right text-xs text-muted-foreground animate-pulse">Loading...</span>
                ) : (
                  <>
                    <IndicatorCell value={ind?.close != null ? formatPrice(ind.close, ind.currency, 0) : null} />
                    <IndicatorCell value={chg.text} className={chg.className} />
                    <IndicatorCell value={rsiVal != null ? rsiVal.toFixed(0) : null} className={rsiColor} />
                    <IndicatorCell
                      value={smaAbove !== null ? (smaAbove ? "Above" : "Below") : null}
                      className={smaAbove === true ? "text-emerald-500" : smaAbove === false ? "text-red-500" : ""}
                    />
                    <IndicatorCell
                      value={macdDir != null ? (macdDir === "bullish" ? "Bull" : "Bear") : null}
                      className={macdDir === "bullish" ? "text-emerald-500" : macdDir === "bearish" ? "text-red-500" : ""}
                    />
                    <IndicatorCell
                      value={bbPos != null ? bbPos.charAt(0).toUpperCase() + bbPos.slice(1) : null}
                      className={
                        bbPos === "above" ? "text-red-500" : bbPos === "below" ? "text-emerald-500" : ""
                      }
                    />
                  </>
                )}
              </div>
            )
          })}
        </div>
      </div>
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
