import { Link } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { AssetActionMenu } from "@/components/asset-action-menu"
import { MarketStatusDot } from "@/components/market-status-dot"
import { DeferredSparkline } from "@/components/sparkline"
import { TagBadge } from "@/components/tag-badge"
import type { AssetType, Quote, TagBrief, SparklinePoint, IndicatorSummary } from "@/lib/api"
import { formatPrice, currencySymbol, changeColor } from "@/lib/format"
import {
  getNumericValue,
  getCardDescriptors,
  resolveThresholdColor,
  resolveAdxColor,
  type IndicatorDescriptor,
} from "@/lib/indicator-registry"
import { usePriceFlash } from "@/lib/use-price-flash"

const CARD_DESCRIPTORS = getCardDescriptors()

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

function MiniIndicatorCard({
  descriptor,
  values,
  currency,
}: {
  descriptor: IndicatorDescriptor
  values?: Record<string, number | string | null>
  currency: string
}) {
  const mainSeries = descriptor.series[0]
  const mainVal = getNumericValue(values, mainSeries.field)

  if (mainVal == null) {
    return (
      <div className="rounded bg-muted/50 px-2 py-1">
        <span className="text-[10px] text-muted-foreground">{descriptor.shortLabel}</span>
        <span className="block text-sm font-semibold tabular-nums text-muted-foreground">--</span>
      </div>
    )
  }

  const colorClass = descriptor.id === "adx"
    ? resolveAdxColor(mainVal, values ?? {})
    : resolveThresholdColor(mainSeries.thresholdColors, mainVal)

  return (
    <div className="rounded bg-muted/50 px-2 py-1">
      <span className="text-[10px] text-muted-foreground">{descriptor.shortLabel}</span>
      <span className={`block text-sm font-semibold tabular-nums ${colorClass || "text-foreground"}`}>
        {currency && descriptor.priceDenominated ? currencySymbol(currency) : ""}{mainVal.toFixed(descriptor.decimals)}
      </span>
      {descriptor.id === "adx" && (
        <div className="flex gap-2 tabular-nums text-[10px] mt-0.5">
          <span className="text-emerald-500">
            +DI {getNumericValue(values, "plus_di")?.toFixed(1) ?? "--"}
          </span>
          <span className="text-red-500">
            -DI {getNumericValue(values, "minus_di")?.toFixed(1) ?? "--"}
          </span>
        </div>
      )}
      {descriptor.id === "macd" && (
        <div className="flex gap-2 tabular-nums text-[10px] mt-0.5">
          <span className="text-sky-400">
            M {getNumericValue(values, "macd")?.toFixed(2) ?? "--"}
          </span>
          <span className="text-orange-400">
            S {getNumericValue(values, "macd_signal")?.toFixed(2) ?? "--"}
          </span>
        </div>
      )}
    </div>
  )
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
  const enabledCards = CARD_DESCRIPTORS.filter(
    (d) => indicatorVisibility[d.id] !== false,
  )
  const lastPrice = quote?.price ?? null
  const changePct = quote?.change_percent ?? null
  const changeCls = changeColor(changePct)

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
              <span ref={pctRef} className={`text-xs font-medium tabular-nums rounded px-1 -mx-1 ${changeCls}`}>
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
          {showSparkline && <DeferredSparkline symbol={symbol} period={sparklinePeriod} batchData={sparklineData} />}
          {enabledCards.length > 0 && (
            <div className="grid grid-cols-2 gap-1.5 mt-1">
              {enabledCards.map((desc) => (
                <MiniIndicatorCard
                  key={desc.id}
                  descriptor={desc}
                  values={indicatorData?.values}
                  currency={currency}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Link>
    </Card>
  )
}
