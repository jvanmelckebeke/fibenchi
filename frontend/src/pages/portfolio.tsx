import { useEffect, useRef, useState } from "react"
import { createChart, type IChartApi, ColorType, AreaSeries } from "lightweight-charts"
import { Link } from "react-router-dom"
import { Loader2, TrendingUp, TrendingDown } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { ChartSkeleton } from "@/components/chart-skeleton"
import { PeriodSelector } from "@/components/period-selector"
import { usePortfolioIndex, usePortfolioPerformers, usePrefetchAssetDetail } from "@/lib/queries"
import { formatChangePct, changeColor } from "@/lib/format"
import { getChartTheme } from "@/lib/chart-utils"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"
import type { AssetPerformance } from "@/lib/api"

export function PortfolioPage() {
  const [period, setPeriod] = useState<string>("1y")
  const { data, isLoading, isFetching } = usePortfolioIndex(period)
  const { data: performers, isLoading: performersLoading } = usePortfolioPerformers(period)

  return (
    <div className="p-6 space-y-8">
      <div className="flex justify-center">
        <PeriodSelector value={period} onChange={setPeriod} />
      </div>

      {isLoading ? (
        <ChartSkeleton height={480} />
      ) : !data || !data.dates.length ? (
        <div className="h-[480px] flex items-center justify-center text-muted-foreground">
          No data yet. Add assets to a group and refresh prices.
        </div>
      ) : (
        <div className="relative">
          {isFetching && (
            <div className="absolute top-0 left-0 right-0 h-0.5 bg-primary/20 overflow-hidden z-10 rounded-t-md">
              <div className="h-full w-1/3 bg-primary animate-[slide_1s_ease-in-out_infinite]" />
            </div>
          )}
          <PortfolioChart dates={data.dates} values={data.values} up={data.change >= 0} />
          <ValueDisplay current={data.current} change={data.change} changePct={data.change_pct} />
        </div>
      )}

      <PerformersSection performers={performers} isLoading={performersLoading} period={period} />
    </div>
  )
}

function PortfolioChart({ dates, values, up }: { dates: string[]; values: number[]; up: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const { startLifecycle } = useChartLifecycle(containerRef, [chartRef])

  useEffect(() => {
    if (!containerRef.current || !dates.length) return

    const theme = getChartTheme()

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 480,
      layout: {
        background: { type: ColorType.Solid, color: theme.bg },
        textColor: theme.text,
        attributionLogo: false,
      },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      crosshair: {
        vertLine: { visible: false },
        horzLine: { visible: false },
      },
      handleScroll: {
        horzTouchDrag: true,
        vertTouchDrag: false,
        mouseWheel: false,
        pressedMouseMove: true,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: false,
        axisDoubleClickReset: { time: true, price: false },
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

    return startLifecycle([chart])
  }, [dates, values, up, startLifecycle])

  return <div ref={containerRef} className="w-full rounded-md overflow-hidden" />
}

function ValueDisplay({ current, change, changePct }: { current: number; change: number; changePct: number }) {
  const sign = change >= 0 ? "+" : ""
  const colorClass = changeColor(change)
  const chg = formatChangePct(changePct)

  return (
    <div className="text-center space-y-1">
      <div className="text-5xl font-light tracking-tight tabular-nums">
        {current.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
      </div>
      <div className={`text-sm font-medium ${colorClass} flex items-center justify-center gap-3`}>
        <span>{sign}{change.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
        <span>{chg.text}</span>
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
  const prefetch = usePrefetchAssetDetail(period)

  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="text-sm font-semibold">{title}</h3>
        <Badge variant="secondary" className="text-xs ml-auto">{period}</Badge>
      </div>
      <div className="space-y-0">
        {assets.map((a) => {
          const chg = formatChangePct(a.change_pct)
          return (
            <Link
              key={a.symbol}
              to={`/asset/${a.symbol}`}
              className="flex items-center justify-between py-2 hover:bg-muted/50 rounded px-2 -mx-2 transition-colors"
              onMouseEnter={() => prefetch(a.symbol)}
            >
              <div className="flex items-center gap-3 min-w-0">
                <span className="font-mono text-sm text-primary">{a.symbol}</span>
                <span className="text-xs text-muted-foreground truncate">{a.name}</span>
              </div>
              <span className={`text-sm font-medium tabular-nums ${chg.className}`}>
                {chg.text}
              </span>
            </Link>
          )
        })}
      </div>
    </Card>
  )
}
