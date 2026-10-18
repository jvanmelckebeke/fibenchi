import { memo } from "react"
import { Link } from "react-router-dom"
import type { Quote } from "@/lib/api"
import type { Asset, IntradayPoint, IndicatorSummary } from "@/lib/types"
import { useIntraday, useIntradaySubscription, useQuoteStatus } from "@/lib/quote-stream"
import { usePriceFlash } from "@/lib/use-price-flash"
import { useSettings } from "@/lib/settings"
import { formatPrice, formatCompactNumber, changeColor } from "@/lib/format"
import { formatDeltaAnnotation } from "@/lib/indicator-registry"
import { marketState } from "@/lib/market-state"
import { ChangePct } from "@/components/change-pct"
import { IntradayChart } from "@/components/chart/intraday-chart"

const DELTA_FIELDS = ["rsi", "macd_hist", "atr", "adx"] as const

interface LiveDayViewProps {
  assets: Asset[]
  quotes: Record<string, Quote>
  indicators?: Record<string, IndicatorSummary>
}

export function LiveDayView({ assets, quotes, indicators }: LiveDayViewProps) {
  // This view is the reason the group's bars are on the wire at all — nothing
  // else in the app draws more than one symbol's worth.
  useIntradaySubscription(assets.map((a) => a.symbol))
  const intraday = useIntraday()

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {assets.map((asset) => (
        <LiveCard
          key={asset.id}
          symbol={asset.symbol}
          name={asset.name}
          currency={asset.currency}
          quote={quotes[asset.symbol]}
          points={intraday[asset.symbol]}
          indicatorData={indicators?.[asset.symbol]}
        />
      ))}
    </div>
  )
}

interface LiveCardProps {
  symbol: string
  name: string
  currency: string
  quote?: Quote
  points?: IntradayPoint[]
  indicatorData?: IndicatorSummary
}

const LiveCard = memo(function LiveCard({
  symbol,
  name,
  currency,
  quote,
  points,
  indicatorData,
}: LiveCardProps) {
  const { settings } = useSettings()
  const quoteStatus = useQuoteStatus()
  const [priceRef, pctRef] = usePriceFlash(quote?.price ?? null)

  const price = quote?.price
  const previousClose = quote?.previous_close
  const changePct = quote?.change_percent
  const volume = quote?.volume
  const marketLabel = marketState(quote?.market_state).label

  return (
    <Link
      to={`/asset/${symbol}`}
      className="block overflow-hidden rounded-lg border bg-card transition-colors hover:border-primary/50">
      {/* Header — ticker, price, change%, market state */}
      <div className="space-y-0.5 px-3 pt-3 pb-1">
        <div className="flex min-w-0 items-baseline justify-between gap-2">
          <div className="flex min-w-0 items-baseline gap-2">
            <span className="truncate text-sm font-semibold">{symbol}</span>
            <span className="truncate text-xs text-muted-foreground">{name}</span>
          </div>
          <div className="flex shrink-0 items-baseline gap-1.5">
            <span
              ref={priceRef}
              className="-mx-0.5 rounded px-0.5 text-sm font-medium tabular-nums">
              {price != null
                ? formatPrice(price, currency, undefined, settings.thousands_separator)
                : "--"}
            </span>
            {changePct != null && (
              <ChangePct
                ref={pctRef}
                value={changePct}
                className="-mx-0.5 rounded px-0.5 text-xs"
              />
            )}
          </div>
        </div>
        <div className="text-xs text-muted-foreground">{marketLabel}</div>
      </div>

      {/* Chart */}
      <div className="mx-3 mb-1 h-[200px] overflow-hidden rounded border border-border/50">
        {points && points.length > 0 ? (
          <IntradayChart points={points} previousClose={previousClose ?? null} />
        ) : quoteStatus === "disconnected" ? (
          <div className="flex h-full flex-col items-center justify-center gap-1.5 text-muted-foreground">
            <div className="h-2 w-2 rounded-full bg-destructive/70" />
            <span className="text-xs">Disconnected</span>
          </div>
        ) : quoteStatus !== "connected" ? (
          <div className="h-full w-full animate-pulse bg-muted/40" />
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-muted-foreground">
            No intraday data
          </div>
        )}
      </div>

      {/* Below chart — indicator deltas + volume */}
      <div className="flex items-baseline justify-between px-3 pt-1 pb-3 text-xs text-muted-foreground">
        {settings.show_indicator_deltas && indicatorData?.values ? (
          <div className="flex flex-wrap gap-x-2 gap-y-0.5">
            {DELTA_FIELDS.map((field) => {
              const ann = formatDeltaAnnotation(field, indicatorData.values)
              if (!ann) return null
              return (
                <span key={field} className="tabular-nums">
                  <span className="uppercase">{field === "macd_hist" ? "MACD H" : field}</span>{" "}
                  <span className={changeColor(parseFloat(ann.delta.replace(/[()]/g, "")))}>
                    {ann.delta}
                  </span>
                  {ann.sigma && (
                    <span className="ml-0.5 text-muted-foreground/60">{ann.sigma}</span>
                  )}
                </span>
              )
            })}
          </div>
        ) : (
          <div />
        )}
        {volume != null && (
          <span className="shrink-0 tabular-nums">Vol: {formatCompactNumber(volume)}</span>
        )}
      </div>
    </Link>
  )
})
