import { useState } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { PriceChart } from "@/components/price-chart"
import { ThesisEditor } from "@/components/thesis-editor"
import { AnnotationsList } from "@/components/annotations-list"
import type { EtfHoldings } from "@/lib/api"
import {
  useAssets,
  usePrices,
  useIndicators,
  useRefreshPrices,
  useEtfHoldings,
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
  const isEtf = asset?.type === "etf"

  if (!symbol) return null

  return (
    <div className="p-6 space-y-6">
      <Header symbol={symbol} period={period} setPeriod={setPeriod} />
      <ChartSection symbol={symbol} period={period} />
      {isEtf && <HoldingsSection symbol={symbol} />}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ThesisSection symbol={symbol} />
        <AnnotationsSection symbol={symbol} />
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

  if (isLoading) {
    return <div className="text-sm text-muted-foreground">Loading holdings...</div>
  }
  if (!data || (!data.top_holdings.length && !data.sector_weightings.length)) {
    return null
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <TopHoldingsCard data={data} />
      <SectorWeightingsCard data={data} />
    </div>
  )
}

function TopHoldingsCard({ data }: { data: EtfHoldings }) {
  return (
    <Card className="p-4">
      <h3 className="text-sm font-semibold mb-3">
        Top {data.top_holdings.length} Holdings ({data.total_percent}% of Total Assets)
      </h3>
      <div className="space-y-0">
        <div className="grid grid-cols-[4rem_1fr_4rem] text-xs text-muted-foreground border-b border-border pb-1 mb-1">
          <span>Symbol</span>
          <span>Company</span>
          <span className="text-right">% Assets</span>
        </div>
        {data.top_holdings.map((h) => (
          <div key={h.symbol} className="grid grid-cols-[4rem_1fr_4rem] text-sm py-1 hover:bg-muted/50 rounded">
            <span className="font-mono text-xs text-primary">{h.symbol}</span>
            <span className="text-muted-foreground truncate text-xs">{h.name}</span>
            <span className="text-right font-medium text-xs">{h.percent.toFixed(2)}%</span>
          </div>
        ))}
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
