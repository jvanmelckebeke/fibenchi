import { useEffect, useRef, useState, useCallback } from "react"
import { createChart, type IChartApi, ColorType, AreaSeries } from "lightweight-charts"
import { Link } from "react-router-dom"
import { Loader2, TrendingUp, TrendingDown } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { usePortfolioIndex, usePortfolioPerformers } from "@/lib/queries"
import type { AssetPerformance } from "@/lib/api"

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"] as const

export function PortfolioPage() {
  const [period, setPeriod] = useState<string>("1y")
  const { data, isLoading } = usePortfolioIndex(period)
  const { data: performers, isLoading: performersLoading } = usePortfolioPerformers(period)

  return (
    <div className="p-6 space-y-8">
      <div className="flex justify-center gap-1">
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

      {isLoading ? (
        <div className="h-[480px] flex flex-col items-center justify-center gap-2 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-sm">Loading portfolio...</span>
        </div>
      ) : !data || !data.dates.length ? (
        <div className="h-[480px] flex items-center justify-center text-muted-foreground">
          No data yet. Add assets to your watchlist and refresh prices.
        </div>
      ) : (
        <>
          <PortfolioChart dates={data.dates} values={data.values} up={data.change >= 0} />
          <ValueDisplay current={data.current} change={data.change} changePct={data.change_pct} />
        </>
      )}

      <PerformersSection performers={performers} isLoading={performersLoading} period={period} />
    </div>
  )
}

function PortfolioChart({ dates, values, up }: { dates: string[]; values: number[]; up: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  const getThemeColors = useCallback(() => {
    const dark = document.documentElement.classList.contains("dark")
    return {
      bg: dark ? "#18181b" : "#ffffff",
      text: dark ? "#a1a1aa" : "#71717a",
    }
  }, [])

  useEffect(() => {
    if (!containerRef.current || !dates.length) return

    const theme = getThemeColors()

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 480,
      layout: {
        background: { type: ColorType.Solid, color: theme.bg },
        textColor: theme.text,
      },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      crosshair: {
        vertLine: { visible: false },
        horzLine: { visible: false },
      },
    })

    const series = chart.addSeries(AreaSeries, {
      lineColor: up ? "#2dd4bf" : "#ef4444",
      topColor: up ? "rgba(45, 212, 191, 0.4)" : "rgba(239, 68, 68, 0.3)",
      bottomColor: up ? "rgba(45, 212, 191, 0.05)" : "rgba(239, 68, 68, 0.05)",
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })

    series.setData(
      dates.map((d, i) => ({ time: d, value: values[i] }))
    )

    chart.timeScale().fitContent()
    chartRef.current = chart

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width })
      }
    })
    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [dates, values, up, getThemeColors])

  return <div ref={containerRef} className="w-full rounded-md overflow-hidden" />
}

function ValueDisplay({ current, change, changePct }: { current: number; change: number; changePct: number }) {
  const positive = change >= 0
  const sign = positive ? "+" : ""
  const colorClass = positive ? "text-emerald-500" : "text-red-500"

  return (
    <div className="text-center space-y-1">
      <div className="text-5xl font-light tracking-tight tabular-nums">
        {current.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>
      <div className={`text-sm font-medium ${colorClass} flex items-center justify-center gap-3`}>
        <span>{sign}{change.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        <span>{sign}{changePct.toFixed(2)}%</span>
      </div>
    </div>
  )
}

function PerformersSection({
  performers,
  isLoading,
  period,
}: {
  performers: AssetPerformance[] | undefined
  isLoading: boolean
  period: string
}) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-muted-foreground py-4">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm">Loading performers...</span>
      </div>
    )
  }

  if (!performers?.length) return null

  const top5 = performers.slice(0, 5)
  const bottom5 = [...performers].reverse().slice(0, 5)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <PerformersList
        title="Top Performers"
        icon={<TrendingUp className="h-4 w-4 text-emerald-500" />}
        assets={top5}
        period={period}
      />
      <PerformersList
        title="Bottom Performers"
        icon={<TrendingDown className="h-4 w-4 text-red-500" />}
        assets={bottom5}
        period={period}
      />
    </div>
  )
}

function PerformersList({
  title,
  icon,
  assets,
  period,
}: {
  title: string
  icon: React.ReactNode
  assets: AssetPerformance[]
  period: string
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-sm font-semibold">{title}</h3>
        <Badge variant="secondary" className="text-xs ml-auto">{period}</Badge>
      </div>
      <div className="space-y-0">
        {assets.map((a) => {
          const positive = a.change_pct >= 0
          const sign = positive ? "+" : ""
          return (
            <Link
              key={a.symbol}
              to={`/asset/${a.symbol}`}
              className="flex items-center justify-between py-2 hover:bg-muted/50 rounded px-2 -mx-2 transition-colors"
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="font-mono text-sm text-primary">{a.symbol}</span>
                <span className="text-xs text-muted-foreground truncate">{a.name}</span>
              </div>
              <span className={`text-sm font-medium tabular-nums ${positive ? "text-emerald-500" : "text-red-500"}`}>
                {sign}{a.change_pct.toFixed(2)}%
              </span>
            </Link>
          )
        })}
      </div>
    </Card>
  )
}
