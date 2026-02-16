import { useState } from "react"
import { Link } from "react-router-dom"
import { ChevronRight, ChevronDown, Trash2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { TagBadge } from "@/components/tag-badge"
import { PriceChart } from "@/components/price-chart"
import { RsiGauge } from "@/components/rsi-gauge"
import { MacdIndicator } from "@/components/macd-indicator"
import type { Asset, Quote, IndicatorSummary } from "@/lib/api"
import { formatPrice } from "@/lib/format"
import { usePriceFlash } from "@/lib/use-price-flash"
import { usePrices, useIndicators, useAnnotations } from "@/lib/queries"
import { useSettings } from "@/lib/settings"

interface WatchlistTableProps {
  assets: Asset[]
  quotes: Record<string, Quote>
  indicators?: Record<string, IndicatorSummary>
  onDelete: (symbol: string) => void
  compactMode: boolean
}

export function WatchlistTable({ assets, quotes, indicators, onDelete, compactMode }: WatchlistTableProps) {
  const [expandedSymbols, setExpandedSymbols] = useState<Set<string>>(new Set())

  const toggleExpand = (symbol: string) => {
    setExpandedSymbols((prev) => {
      const next = new Set(prev)
      if (next.has(symbol)) next.delete(symbol)
      else next.add(symbol)
      return next
    })
  }

  return (
    <div className="rounded-md border border-border overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            <th className="w-8" />
            <th className="text-left text-xs font-medium text-muted-foreground px-3 py-2">Symbol</th>
            <th className="text-left text-xs font-medium text-muted-foreground px-3 py-2">Name</th>
            <th className="text-right text-xs font-medium text-muted-foreground px-3 py-2">Price</th>
            <th className="text-right text-xs font-medium text-muted-foreground px-3 py-2">Change</th>
            <th className="text-right text-xs font-medium text-muted-foreground px-3 py-2">RSI</th>
            <th className="text-right text-xs font-medium text-muted-foreground px-3 py-2">MACD</th>
            <th className="text-right text-xs font-medium text-muted-foreground px-3 py-2">Signal</th>
            <th className="text-right text-xs font-medium text-muted-foreground px-3 py-2">Hist</th>
            <th className="w-8" />
          </tr>
        </thead>
        <tbody>
          {assets.map((asset) => (
            <TableRow
              key={asset.id}
              asset={asset}
              quote={quotes[asset.symbol]}
              indicator={indicators?.[asset.symbol]}
              expanded={expandedSymbols.has(asset.symbol)}
              onToggle={() => toggleExpand(asset.symbol)}
              onDelete={() => onDelete(asset.symbol)}
              compactMode={compactMode}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function getRsiColor(rsi: number): string {
  if (rsi <= 30) return "text-amber-400"
  if (rsi >= 70) return "text-orange-400"
  return ""
}

function ExpandedContent({ symbol, indicator }: { symbol: string; indicator?: IndicatorSummary }) {
  const { settings } = useSettings()
  const period = settings.chart_default_period
  const { data: prices, isLoading: pricesLoading } = usePrices(symbol, period)
  const { data: chartIndicators, isLoading: indicatorsLoading } = useIndicators(symbol, period)
  const { data: annotations } = useAnnotations(symbol)

  const loading = pricesLoading || indicatorsLoading

  return (
    <div className="flex gap-4">
      {/* Price chart — 80% */}
      <div className="flex-[4] min-w-0">
        {loading || !prices?.length ? (
          <div className="h-[300px] flex items-center justify-center">
            <Skeleton className="h-full w-full rounded-md" />
          </div>
        ) : (
          <PriceChart
            prices={prices}
            indicators={chartIndicators ?? []}
            annotations={annotations ?? []}
            showSma20={settings.detail_show_sma20}
            showSma50={settings.detail_show_sma50}
            showBollinger={settings.detail_show_bollinger}
            showRsiChart={false}
            showMacdChart={false}
            chartType={settings.chart_type}
            mainChartHeight={300}
          />
        )}
      </div>
      {/* Indicators — 20% */}
      <div className="flex-1 flex flex-col gap-3 justify-center min-w-[140px] max-w-[200px]">
        <div>
          <span className="text-xs text-muted-foreground mb-1 block">RSI</span>
          <RsiGauge symbol={symbol} batchRsi={indicator?.rsi} size="lg" />
        </div>
        <div>
          <span className="text-xs text-muted-foreground mb-1 block">MACD</span>
          <MacdIndicator
            symbol={symbol}
            batchMacd={indicator ? { macd: indicator.macd, macd_signal: indicator.macd_signal, macd_hist: indicator.macd_hist } : undefined}
            size="lg"
          />
        </div>
      </div>
    </div>
  )
}

function TableRow({
  asset,
  quote,
  indicator,
  expanded,
  onToggle,
  onDelete,
  compactMode,
}: {
  asset: Asset
  quote?: Quote
  indicator?: IndicatorSummary
  expanded: boolean
  onToggle: () => void
  onDelete: () => void
  compactMode: boolean
}) {
  const lastPrice = quote?.price ?? null
  const changePct = quote?.change_percent ?? null
  const changeColor =
    changePct != null ? (changePct >= 0 ? "text-emerald-500" : "text-red-500") : "text-muted-foreground"

  const [priceRef, pctRef] = usePriceFlash(lastPrice)
  const py = compactMode ? "py-1.5" : "py-2.5"

  return (
    <>
      <tr
        className="border-b border-border hover:bg-muted/30 cursor-pointer group transition-colors"
        onClick={onToggle}
      >
        <td className={`${py} pl-2`}>
          {expanded ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </td>
        <td className={`${py} px-3`}>
          <div className="flex items-center gap-2">
            <Link
              to={`/asset/${asset.symbol}`}
              className="font-semibold hover:underline"
              onClick={(e) => e.stopPropagation()}
            >
              {asset.symbol}
            </Link>
            <Badge variant="secondary" className="text-[10px] px-1 py-0">
              {asset.type}
            </Badge>
          </div>
        </td>
        <td className={`${py} px-3 text-sm text-muted-foreground max-w-[250px]`}>
          <div className="flex items-center gap-2 truncate">
            <span className="truncate">{asset.name}</span>
            {asset.tags.length > 0 && (
              <span className="flex gap-1 shrink-0">
                {asset.tags.map((tag) => (
                  <TagBadge key={tag.id} name={tag.name} color={tag.color} />
                ))}
              </span>
            )}
          </div>
        </td>
        <td className={`${py} px-3 text-right tabular-nums`}>
          {lastPrice != null ? (
            <span ref={priceRef} className="font-medium rounded px-1 -mx-1">
              {formatPrice(lastPrice, asset.currency)}
            </span>
          ) : (
            <Skeleton className="h-4 w-14 ml-auto rounded" />
          )}
        </td>
        <td className={`${py} px-3 text-right tabular-nums`}>
          {changePct != null ? (
            <span ref={pctRef} className={`font-medium rounded px-1 -mx-1 ${changeColor}`}>
              {changePct >= 0 ? "+" : ""}
              {changePct.toFixed(2)}%
            </span>
          ) : (
            <Skeleton className="h-4 w-12 ml-auto rounded" />
          )}
        </td>
        <td className={`${py} px-3 text-right text-sm tabular-nums`}>
          {indicator?.rsi != null ? (
            <span className={getRsiColor(indicator.rsi)}>{indicator.rsi.toFixed(0)}</span>
          ) : (
            <span className="text-muted-foreground">&mdash;</span>
          )}
        </td>
        <td className={`${py} px-3 text-right text-sm tabular-nums`}>
          {indicator?.macd != null ? (
            indicator.macd.toFixed(2)
          ) : (
            <span className="text-muted-foreground">&mdash;</span>
          )}
        </td>
        <td className={`${py} px-3 text-right text-sm tabular-nums`}>
          {indicator?.macd_signal != null ? (
            indicator.macd_signal.toFixed(2)
          ) : (
            <span className="text-muted-foreground">&mdash;</span>
          )}
        </td>
        <td className={`${py} px-3 text-right text-sm tabular-nums`}>
          {indicator?.macd_hist != null ? (
            <span className={indicator.macd_hist >= 0 ? "text-emerald-400" : "text-red-400"}>
              {indicator.macd_hist >= 0 ? "+" : ""}
              {indicator.macd_hist.toFixed(2)}
            </span>
          ) : (
            <span className="text-muted-foreground">&mdash;</span>
          )}
        </td>
        <td className={`${py} pr-2`}>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
          >
            <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive" />
          </Button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={10} className="bg-muted/20 p-4 border-b border-border">
            <ExpandedContent symbol={asset.symbol} indicator={indicator} />
          </td>
        </tr>
      )}
    </>
  )
}
