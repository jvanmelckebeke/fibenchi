import { useEffect, useRef, useState, useCallback } from "react"
import { createChart, type IChartApi, ColorType, AreaSeries } from "lightweight-charts"
import { Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { usePortfolioIndex } from "@/lib/queries"

const PERIODS = ["1mo", "3mo", "6mo", "1y", "2y", "5y"] as const

export function PortfolioPage() {
  const [period, setPeriod] = useState<string>("1y")
  const { data, isLoading } = usePortfolioIndex(period)

  return (
    <div className="flex flex-col items-center justify-center min-h-screen p-6">
      <div className="w-full max-w-3xl space-y-6">
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
          <div className="h-[300px] flex flex-col items-center justify-center gap-2 text-muted-foreground">
            <Loader2 className="h-6 w-6 animate-spin" />
            <span className="text-sm">Loading portfolio...</span>
          </div>
        ) : !data || !data.dates.length ? (
          <div className="h-[300px] flex items-center justify-center text-muted-foreground">
            No data yet. Add assets to your watchlist and refresh prices.
          </div>
        ) : (
          <>
            <PortfolioChart dates={data.dates} values={data.values} up={data.change >= 0} />
            <ValueDisplay current={data.current} change={data.change} changePct={data.change_pct} />
          </>
        )}
      </div>
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
      height: 300,
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
