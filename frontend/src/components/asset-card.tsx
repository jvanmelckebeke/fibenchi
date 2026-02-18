import { Link } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { AssetActionMenu } from "@/components/asset-action-menu"
import { MarketStatusDot } from "@/components/market-status-dot"
import { SparklineChart } from "@/components/sparkline"
import { RsiGauge } from "@/components/rsi-gauge"
import { MacdIndicator } from "@/components/macd-indicator"
import { TagBadge } from "@/components/tag-badge"
import type { AssetType, Quote, TagBrief, SparklinePoint, IndicatorSummary } from "@/lib/api"
import { formatPrice } from "@/lib/format"
import { getNumericValue } from "@/lib/indicator-registry"
import { usePriceFlash } from "@/lib/use-price-flash"

export interface AssetCardProps {
  symbol: string
  name: string
  type: AssetType
  currency: string
  tags: TagBrief[]
  quote?: Quote
  sparklinePeriod: string
  sparklineData?: SparklinePoint[]
  indicatorData?: IndicatorSummary
  onDelete: () => void
  onHover: () => void
  showSparkline: boolean
  indicatorVisibility: Record<string, boolean>
}

export function AssetCard({
  symbol,
  name,
  type,
  currency,
  tags,
  quote,
  sparklinePeriod,
  sparklineData,
  indicatorData,
  onDelete,
  onHover,
  showSparkline,
  indicatorVisibility,
}: AssetCardProps) {
  const showRsi = indicatorVisibility.rsi !== false
  const showMacd = indicatorVisibility.macd !== false
  const lastPrice = quote?.price ?? null
  const changePct = quote?.change_percent ?? null
  const changeColor =
    changePct != null ? (changePct >= 0 ? "text-green-500" : "text-red-500") : "text-muted-foreground"

  const [priceRef, pctRef] = usePriceFlash(lastPrice)

  return (
    <Card className="group relative hover:border-primary/50 transition-colors" onMouseEnter={onHover}>
      <AssetActionMenu
        onDelete={onDelete}
        triggerClassName="absolute right-2 top-2 h-7 w-7 opacity-0 group-hover:opacity-100 z-10"
      />
      <Link to={`/asset/${symbol}`}>
        <CardHeader className="pb-2">
          <div className="flex items-center gap-2">
            <MarketStatusDot marketState={quote?.market_state} />
            <CardTitle className="text-base">{symbol}</CardTitle>
            <Badge variant="secondary" className="text-xs">
              {type}
            </Badge>
            {lastPrice != null ? (
              <span ref={priceRef} className="ml-auto text-base font-semibold tabular-nums rounded px-1 -mx-1">
                {formatPrice(lastPrice, currency)}
              </span>
            ) : (
              <Skeleton className="ml-auto h-5 w-16 rounded" />
            )}
          </div>
          <div className="flex items-center justify-between">
            <p className="text-xs text-muted-foreground truncate">{name}</p>
            {changePct != null ? (
              <span ref={pctRef} className={`text-xs font-medium tabular-nums rounded px-1 -mx-1 ${changeColor}`}>
                {changePct >= 0 ? "+" : ""}
                {changePct.toFixed(2)}%
              </span>
            ) : (
              <Skeleton className="h-3.5 w-12 rounded" />
            )}
          </div>
          {tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {tags.map((tag) => (
                <TagBadge key={tag.id} name={tag.name} color={tag.color} />
              ))}
            </div>
          )}
        </CardHeader>
        <CardContent className="pt-0 space-y-2">
          {showSparkline && <SparklineChart symbol={symbol} period={sparklinePeriod} batchData={sparklineData} />}
          {(showRsi || showMacd) && (
            <div className="flex gap-1.5 mt-1">
              {showRsi && <RsiGauge batchRsi={getNumericValue(indicatorData?.values, "rsi")} />}
              {showMacd && <MacdIndicator batchMacd={indicatorData?.values ? { macd: getNumericValue(indicatorData.values, "macd"), macd_signal: getNumericValue(indicatorData.values, "macd_signal"), macd_hist: getNumericValue(indicatorData.values, "macd_hist") } : undefined} />}
            </div>
          )}
        </CardContent>
      </Link>
    </Card>
  )
}
