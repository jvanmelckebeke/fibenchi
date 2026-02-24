import { Link } from "react-router-dom"
import { ArrowLeft, ExternalLink, RefreshCw, Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { PeriodSelector } from "@/components/period-selector"
import { MarketStatusDot } from "@/components/market-status-dot"
import { buildYahooFinanceUrl, formatPrice, formatCompactPrice, formatChangePct } from "@/lib/format"
import { useQuotes } from "@/lib/quote-stream"
import { usePriceFlash } from "@/lib/use-price-flash"
import { useRefreshPrices, useCreateAsset } from "@/lib/queries"
import { useSettings } from "@/lib/settings"

export function Header({
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
  const { settings } = useSettings()
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
          <span
            ref={priceRef}
            className="text-xl font-semibold tabular-nums rounded px-1"
            title={settings.compact_numbers ? formatPrice(price, currency) : undefined}
          >
            {settings.compact_numbers
              ? formatCompactPrice(price, currency)
              : formatPrice(price, currency)}
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
