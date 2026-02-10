import { useEffect, useRef } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  createChart,
  type IChartApi,
  ColorType,
  LineSeries,
} from "lightweight-charts"
import { usePseudoEtf, usePseudoEtfPerformance } from "@/lib/queries"

export function PseudoEtfDetailPage() {
  const { id } = useParams<{ id: string }>()
  const etfId = Number(id)
  const { data: etf } = usePseudoEtf(etfId)
  const { data: performance, isLoading } = usePseudoEtfPerformance(etfId)

  if (!etf) return null

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/pseudo-etfs">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-4 w-4" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">{etf.name}</h1>
          {etf.description && <p className="text-sm text-muted-foreground">{etf.description}</p>}
        </div>
      </div>

      <div className="flex items-center gap-4 text-sm text-muted-foreground">
        <span>Base: {etf.base_date} = {etf.base_value}</span>
        <span>Constituents: {etf.constituents.length}</span>
      </div>

      <div className="flex flex-wrap gap-2">
        {etf.constituents.map((a) => (
          <Link key={a.id} to={`/asset/${a.symbol}`}>
            <Badge variant="secondary" className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors">
              {a.symbol}
            </Badge>
          </Link>
        ))}
      </div>

      {isLoading && <p className="text-muted-foreground">Calculating performance...</p>}

      {performance && performance.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Performance (indexed to {etf.base_value})</CardTitle>
          </CardHeader>
          <CardContent>
            <PerformanceChart data={performance} baseValue={etf.base_value} />
            <PerformanceStats data={performance} baseValue={etf.base_value} />
          </CardContent>
        </Card>
      )}

      {performance && performance.length === 0 && (
        <p className="text-muted-foreground">
          No performance data. Make sure constituent stocks have price history from {etf.base_date}.
        </p>
      )}
    </div>
  )
}

function PerformanceChart({ data, baseValue }: { data: { date: string; value: number }[]; baseValue: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!ref.current || !data.length) return

    const dark = document.documentElement.classList.contains("dark")

    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 400,
      layout: {
        background: { type: ColorType.Solid, color: dark ? "#18181b" : "#ffffff" },
        textColor: dark ? "#a1a1aa" : "#71717a",
      },
      grid: {
        vertLines: { color: dark ? "#27272a" : "#f4f4f5" },
        horzLines: { color: dark ? "#27272a" : "#f4f4f5" },
      },
      rightPriceScale: { borderColor: dark ? "#3f3f46" : "#e4e4e7" },
      timeScale: { borderColor: dark ? "#3f3f46" : "#e4e4e7", timeVisible: false },
    })

    const last = data[data.length - 1]
    const up = last.value >= baseValue
    const color = up ? "#22c55e" : "#ef4444"

    const series = chart.addSeries(LineSeries, {
      color,
      lineWidth: 2,
      priceLineVisible: true,
    })

    series.setData(data.map((p) => ({ time: p.date, value: p.value })))

    // Base value reference line
    const baseLine = chart.addSeries(LineSeries, {
      color: dark ? "rgba(161, 161, 170, 0.3)" : "rgba(113, 113, 122, 0.3)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })
    baseLine.setData(data.map((p) => ({ time: p.date, value: baseValue })))

    chart.timeScale().fitContent()
    chartRef.current = chart

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width })
      }
    })
    resizeObserver.observe(ref.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [data, baseValue])

  return <div ref={ref} className="w-full" />
}

function PerformanceStats({ data, baseValue }: { data: { date: string; value: number }[]; baseValue: number }) {
  if (!data.length) return null

  const last = data[data.length - 1]
  const totalReturn = ((last.value - baseValue) / baseValue) * 100

  return (
    <div className="flex gap-6 mt-3 text-sm">
      <div>
        <span className="text-muted-foreground">Current: </span>
        <span className="font-medium">{last.value.toFixed(2)}</span>
      </div>
      <div>
        <span className="text-muted-foreground">Total return: </span>
        <span className={`font-medium ${totalReturn >= 0 ? "text-green-500" : "text-red-500"}`}>
          {totalReturn >= 0 ? "+" : ""}{totalReturn.toFixed(1)}%
        </span>
      </div>
      <div>
        <span className="text-muted-foreground">Period: </span>
        <span className="font-medium">{data[0].date} to {last.date}</span>
      </div>
    </div>
  )
}
