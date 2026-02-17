import { useState } from "react"
import { Link } from "react-router-dom"
import { ChevronRight, ChevronDown } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { TagBadge } from "@/components/tag-badge"
import { AssetActionMenu } from "@/components/asset-action-menu"
import { MarketStatusDot } from "@/components/market-status-dot"
import { PriceChart } from "@/components/price-chart"
import { RsiGauge } from "@/components/rsi-gauge"
import { MacdIndicator } from "@/components/macd-indicator"
import { ArrowUp, ArrowDown } from "lucide-react"
import type { Asset, Quote, IndicatorSummary } from "@/lib/api"
import type { WatchlistSortBy, SortDir } from "@/lib/settings"
import { formatPrice } from "@/lib/format"
import { usePriceFlash } from "@/lib/use-price-flash"
import { useAssetDetail, useAnnotations } from "@/lib/queries"
import { useSettings } from "@/lib/settings"

interface WatchlistTableProps {
  assets: Asset[]
  quotes: Record<string, Quote>
  indicators?: Record<string, IndicatorSummary>
  onDelete: (symbol: string) => void
  compactMode: boolean
  onHover?: (symbol: string) => void
  sortBy?: WatchlistSortBy
  sortDir?: SortDir
  onSort?: (key: WatchlistSortBy) => void
}

export function WatchlistTable({ assets, quotes, indicators, onDelete, compactMode, onHover, sortBy, sortDir, onSort }: WatchlistTableProps) {
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
            <SortableHeader label="Symbol" sortKey="name" align="left" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
            <th className="text-left text-xs font-medium text-muted-foreground px-3 py-2">Name</th>
            <SortableHeader label="Price" sortKey="price" align="right" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
            <SortableHeader label="Change" sortKey="change_pct" align="right" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
            <SortableHeader label="RSI" sortKey="rsi" align="right" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
            <SortableHeader label="MACD" sortKey="macd" align="right" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
            <SortableHeader label="Signal" sortKey="macd_signal" align="right" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
            <SortableHeader label="Hist" sortKey="macd_hist" align="right" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
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
              onHover={() => onHover?.(asset.symbol)}
              compactMode={compactMode}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SortableHeader({
  label,
  sortKey,
  align,
  sortBy,
  sortDir,
  onSort,
}: {
  label: string
  sortKey: WatchlistSortBy
  align: "left" | "right"
  sortBy?: WatchlistSortBy
  sortDir?: SortDir
  onSort?: (key: WatchlistSortBy) => void
}) {
  const active = sortBy === sortKey
  const Icon = active && sortDir === "asc" ? ArrowUp : ArrowDown

  return (
    <th
      className={`text-${align} text-xs font-medium px-3 py-2 ${
        onSort ? "cursor-pointer select-none hover:text-foreground" : ""
      } ${active ? "text-foreground" : "text-muted-foreground"}`}
      onClick={() => onSort?.(sortKey)}
    >
      <span className={`inline-flex items-center gap-0.5 ${align === "right" ? "justify-end" : ""}`}>
        {label}
        {active && <Icon className="h-3 w-3" />}
      </span>
    </th>
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
  const { data: detail, isLoading: detailLoading } = useAssetDetail(symbol, period)
  const prices = detail?.prices
  const chartIndicators = detail?.indicators
  const { data: annotations } = useAnnotations(symbol)

  const loading = detailLoading

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
  onHover,
  compactMode,
}: {
  asset: Asset
  quote?: Quote
  indicator?: IndicatorSummary
  expanded: boolean
  onToggle: () => void
  onDelete: () => void
  onHover: () => void
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
        onMouseEnter={onHover}
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
            <MarketStatusDot marketState={quote?.market_state} />
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
          <AssetActionMenu
            onDelete={onDelete}
            triggerClassName="h-6 w-6 opacity-0 group-hover:opacity-100"
          />
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
