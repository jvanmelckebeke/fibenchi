import { Link } from "react-router-dom"
import { ChevronRight, ChevronDown } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"
import { ContextMenu, ContextMenuTrigger } from "@/components/ui/context-menu"
import { AssetContextMenuContent } from "@/components/asset-context-menu"
import { TagBadge } from "@/components/tag-badge"
import { MarketStatusDot } from "@/components/market-status-dot"
import { ExpandedAssetChart } from "@/components/expanded-asset-chart"
import type { Asset, Quote, IndicatorSummary } from "@/lib/api"
import { formatPrice, changeColor, formatChangePct } from "@/lib/format"
import {
  getNumericValue,
  extractMacdValues,
  getSeriesByField,
  resolveThresholdColor,
  resolveAdxColor,
} from "@/lib/indicator-registry"
import { usePriceFlash } from "@/lib/use-price-flash"
import { isColumnVisible } from "./shared"

export function TableRow({
  groupId,
  asset,
  quote,
  indicator,
  expanded,
  onToggle,
  onDelete,
  onHover,
  compactMode,
  columnSettings,
  visibleIndicatorFields,
  totalColSpan,
}: {
  groupId: number
  asset: Asset
  quote?: Quote
  indicator?: IndicatorSummary
  expanded: boolean
  onToggle: () => void
  onDelete: () => void
  onHover: () => void
  compactMode: boolean
  columnSettings: Record<string, boolean>
  visibleIndicatorFields: string[]
  totalColSpan: number
}) {
  // Use live SSE quote when available, fall back to DB-cached indicator values
  const livePrice = quote?.price ?? null
  const livePct = quote?.change_percent ?? null
  const displayPrice = livePrice ?? indicator?.close ?? null
  const displayPct = livePct ?? indicator?.change_pct ?? null
  const changeCls = changeColor(displayPct)

  // Stale = we have DB data but no live quote yet
  const hasLiveQuote = livePrice != null
  const hasDbFallback = !hasLiveQuote && displayPrice != null
  // Suppress stale indicator when market is closed — DB prices are already current.
  // When no quote yet, market_state is unknown so we assume market hours (show stale).
  const marketState = quote?.market_state
  const isMarketClosed = marketState === "CLOSED" || marketState === "POSTMARKET"
  const showStale = hasDbFallback && !isMarketClosed

  const [priceRef, pctRef] = usePriceFlash(displayPrice)
  const py = compactMode ? "py-1.5" : "py-2.5"
  const staleClass = showStale ? "stale-price" : ""

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <tr
          className="border-b border-border hover:bg-muted/30 data-[state=open]:bg-muted/30 cursor-pointer group transition-colors"
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
          {isColumnVisible(columnSettings, "name") && (
            <td className={`${py} px-3 text-sm text-muted-foreground`}>
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
          )}
          {isColumnVisible(columnSettings, "price") && (
            <td className={`${py} px-3 text-right tabular-nums`}>
              {displayPrice != null ? (
                <span ref={priceRef} className={`font-medium rounded px-1 -mx-1 ${staleClass}`}>
                  {formatPrice(displayPrice, asset.currency)}
                </span>
              ) : (
                <Skeleton className="h-4 w-14 ml-auto rounded" />
              )}
            </td>
          )}
          {isColumnVisible(columnSettings, "change_pct") && (
            <td className={`${py} px-3 text-right tabular-nums`}>
              {displayPct != null ? (
                <span ref={pctRef} className={`font-medium rounded px-1 -mx-1 ${changeCls} ${staleClass}`}>
                  {formatChangePct(displayPct).text}
                </span>
              ) : (
                <Skeleton className="h-4 w-12 ml-auto rounded" />
              )}
            </td>
          )}
          {visibleIndicatorFields.map((field) => {
            if (field === "macd") {
              const macdVals = extractMacdValues(indicator?.values)
              const m = macdVals?.macd
              const s = macdVals?.macd_signal
              const h = macdVals?.macd_hist
              const hasValues = m != null || s != null || h != null
              const histColor = h != null ? (h >= 0 ? "text-emerald-400" : "text-red-400") : ""
              const fmt = (v: number | null | undefined) =>
                v != null ? v.toFixed(Math.abs(v) >= 100 ? 0 : 2) : "--"
              return (
                <td key={field} className={`${py} px-3 text-right text-sm tabular-nums overflow-hidden`}>
                  {hasValues ? (
                    <span className="inline-flex items-center gap-2">
                      <span className="text-muted-foreground">M</span>
                      <span>{fmt(m)}</span>
                      <span className="text-muted-foreground">S</span>
                      <span>{fmt(s)}</span>
                      <span className="text-muted-foreground">H</span>
                      <span className={histColor}>{fmt(h)}</span>
                    </span>
                  ) : (
                    <span className="text-muted-foreground">&mdash;</span>
                  )}
                </td>
              )
            }
            const val = getNumericValue(indicator?.values, field)
            const series = getSeriesByField(field)
            const colorClass = field === "adx" && val != null && indicator?.values
              ? resolveAdxColor(val, indicator.values)
              : resolveThresholdColor(series?.thresholdColors, val)
            const decimals = val != null && Math.abs(val) >= 100 ? 0 : 2
            return (
              <td key={field} className={`${py} px-3 text-right text-sm tabular-nums`}>
                {val != null ? (
                  <span className={colorClass}>{val.toFixed(decimals)}</span>
                ) : (
                  <span className="text-muted-foreground">&mdash;</span>
                )}
              </td>
            )
          })}
          <td className={`${py} pr-2`} />
        </tr>
      </ContextMenuTrigger>
      <AssetContextMenuContent
        groupId={groupId}
        assetId={asset.id}
        symbol={asset.symbol}
        onRemove={onDelete}
      />
      {expanded && (
        <tr>
          <td colSpan={totalColSpan} className="bg-muted/20 p-4 border-b border-border">
            <div className="max-w-[calc(100vw-4rem)]">
              <ExpandedAssetChart symbol={asset.symbol} currency={asset.currency} compact />
            </div>
          </td>
        </tr>
      )}
    </ContextMenu>
  )
}
