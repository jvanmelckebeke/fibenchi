import { Link } from "react-router-dom"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { ContextMenu, ContextMenuTrigger } from "@/components/ui/context-menu"
import { AssetContextMenuContent } from "@/components/asset-context-menu"
import { MarketStatusDot } from "@/components/market-status-dot"
import { DeferredSparkline } from "@/components/sparkline"
import { TagBadge } from "@/components/tag-badge"
import type { AssetType, Quote, TagBrief, SparklinePoint, IndicatorSummary } from "@/lib/api"
import { formatPrice, formatCompactPrice, changeColor, formatChangePct } from "@/lib/format"
import { getCardDescriptors, isVisibleAt, type IndicatorDescriptor, type Placement } from "@/lib/indicator-registry"
import { IndicatorValue } from "@/components/indicator-value"
import { usePriceFlash } from "@/lib/use-price-flash"
import { useSettings } from "@/lib/settings"

const CARD_DESCRIPTORS = getCardDescriptors()

export interface AssetCardProps {
  groupId: number
  assetId: number
  symbol: string
  name: string
  type: AssetType
  currency: string
  tags: TagBrief[]
  quote?: Quote
  sparklineData?: SparklinePoint[]
  indicatorData?: IndicatorSummary
  onDelete: () => void
  onHover: () => void
  showSparkline: boolean
  indicatorVisibility: Record<string, Placement[]>
}

function MiniIndicatorCard({
  descriptor,
  values,
  currency,
  expanded,
}: {
  descriptor: IndicatorDescriptor
  values?: Record<string, number | string | null>
  currency: string
  expanded?: boolean
}) {
  return (
    <div className={`rounded bg-muted/50 px-2 py-1 ${expanded ? "text-center" : ""}`}>
      <span className="text-[10px] text-muted-foreground">{descriptor.shortLabel}</span>
      <IndicatorValue descriptor={descriptor} values={values} currency={currency} compact expanded={expanded} />
    </div>
  )
}

export function AssetCard({
  groupId,
  assetId,
  symbol,
  name,
  type,
  currency,
  tags,
  quote,
  sparklineData,
  indicatorData,
  onDelete,
  onHover,
  showSparkline,
  indicatorVisibility,
}: AssetCardProps) {
  const { settings } = useSettings()
  const enabledCards = CARD_DESCRIPTORS.filter(
    (d) => isVisibleAt(indicatorVisibility, d.id, "group_card"),
  )
  const lastPrice = quote?.price ?? null
  const changePct = quote?.change_percent ?? null
  const changeCls = changeColor(changePct)

  const [priceRef, pctRef] = usePriceFlash(lastPrice)

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <Card className="group relative hover:border-primary/50 data-[state=open]:border-primary/50 transition-colors" onMouseEnter={onHover}>
          <Link to={`/asset/${symbol}`}>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <MarketStatusDot marketState={quote?.market_state} />
                <CardTitle className="text-base">{symbol}</CardTitle>
                <Badge variant="secondary" className="text-xs">
                  {type}
                </Badge>
                {lastPrice != null ? (
                  <span
                    ref={priceRef}
                    className="ml-auto text-base font-semibold tabular-nums rounded px-1 -mx-1"
                    title={settings.compact_numbers ? formatPrice(lastPrice, currency) : undefined}
                  >
                    {settings.compact_numbers
                      ? formatCompactPrice(lastPrice, currency)
                      : formatPrice(lastPrice, currency)}
                  </span>
                ) : (
                  <Skeleton className="ml-auto h-5 w-16 rounded" />
                )}
              </div>
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground truncate">{name}</p>
                {changePct != null ? (
                  <span ref={pctRef} className={`text-xs font-medium tabular-nums rounded px-1 -mx-1 ${changeCls}`}>
                    {formatChangePct(changePct).text}
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
              {showSparkline && <DeferredSparkline batchData={sparklineData} />}
              {enabledCards.length > 0 && (
                <div
                  className="gap-1.5 mt-1 grid"
                  style={{ gridTemplateColumns: enabledCards.length === 1 ? "1fr" : "1fr 1fr" }}
                >
                  {enabledCards.map((desc) => (
                    <MiniIndicatorCard
                      key={desc.id}
                      descriptor={desc}
                      values={indicatorData?.values}
                      currency={currency}
                      expanded={enabledCards.length === 1}
                    />
                  ))}
                </div>
              )}
            </CardContent>
          </Link>
        </Card>
      </ContextMenuTrigger>
      <AssetContextMenuContent
        groupId={groupId}
        assetId={assetId}
        symbol={symbol}
        onRemove={onDelete}
      />
    </ContextMenu>
  )
}
