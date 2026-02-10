import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { PriceChart } from "@/components/price-chart"
import { ThesisEditor } from "@/components/thesis-editor"
import { AnnotationsList } from "@/components/annotations-list"
import { usePrices, useIndicators, useRefreshPrices, useAnnotations } from "@/lib/queries"

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"] as const

export function AssetDetailPage() {
  const { symbol } = useParams<{ symbol: string }>()
  const [period, setPeriod] = useState<string>("1y")

  if (!symbol) return null

  return (
    <div className="p-6 space-y-6">
      <Header symbol={symbol} period={period} setPeriod={setPeriod} />
      <ChartSection symbol={symbol} period={period} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ThesisEditor symbol={symbol} />
        <AnnotationsList symbol={symbol} />
      </div>
    </div>
  )
}

function Header({
  symbol,
  period,
  setPeriod,
}: {
  symbol: string
  period: string
  setPeriod: (p: string) => void
}) {
  const refresh = useRefreshPrices(symbol)

  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-3">
        <Link to="/">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <h1 className="text-2xl font-bold">{symbol}</h1>
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
        <Button
          variant="outline"
          size="sm"
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending}
        >
          <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${refresh.isPending ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>
    </div>
  )
}

function ChartSection({ symbol, period }: { symbol: string; period: string }) {
  const { data: prices, isLoading: pricesLoading } = usePrices(symbol, period)
  const { data: indicators, isLoading: indicatorsLoading } = useIndicators(symbol, period)
  const { data: annotations } = useAnnotations(symbol)

  if (pricesLoading || indicatorsLoading) {
    return <div className="h-[520px] flex items-center justify-center text-muted-foreground">Loading chart...</div>
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
