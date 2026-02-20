import { useState, useEffect, useRef, useMemo } from "react"
import {
  createChart,
  type IChartApi,
  HistogramSeries,
} from "lightweight-charts"
import { baseChartOptions, STACK_COLORS } from "@/lib/chart-utils"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"
import type { PerformanceBreakdownPoint } from "@/lib/api"
import { SymbolLegend } from "./symbol-legend"

interface SharedChartProps {
  data: PerformanceBreakdownPoint[]
  sortedSymbols: string[]
  symbolColorMap: Map<string, string>
}

export function DailyContributionChart({ data, sortedSymbols, symbolColorMap }: SharedChartProps) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const [hoverData, setHoverData] = useState<{ date: string; deltas: Record<string, number>; total: number } | null>(null)
  const { startLifecycle } = useChartLifecycle(ref, [chartRef])

  const deltasByTime = useRef(new Map<string, Record<string, number>>())

  useEffect(() => {
    if (!ref.current || data.length < 2 || !sortedSymbols.length) return

    deltasByTime.current.clear()

    // Compute daily deltas per symbol
    const dailyData: { date: string; deltas: Record<string, number> }[] = []
    for (let d = 1; d < data.length; d++) {
      const deltas: Record<string, number> = {}
      for (const sym of sortedSymbols) {
        deltas[sym] = (data[d].breakdown[sym] ?? 0) - (data[d - 1].breakdown[sym] ?? 0)
      }
      dailyData.push({ date: data[d].date, deltas })
      deltasByTime.current.set(data[d].date, deltas)
    }

    // Compute positive and negative cumulative stacks per day
    const posCum: number[][] = []
    const negCum: number[][] = []
    for (const { deltas } of dailyData) {
      const pos: number[] = []
      const neg: number[] = []
      let posSum = 0
      let negSum = 0
      for (const sym of sortedSymbols) {
        const delta = deltas[sym]
        if (delta > 0) posSum += delta
        if (delta < 0) negSum += delta
        pos.push(posSum)
        neg.push(negSum)
      }
      posCum.push(pos)
      negCum.push(neg)
    }

    const chart = createChart(ref.current, baseChartOptions(ref.current, 250))

    // Draw positive stack: outermost first (i = N-1 -> 0)
    for (let i = sortedSymbols.length - 1; i >= 0; i--) {
      const sym = sortedSymbols[i]
      const color = symbolColorMap.get(sym) ?? STACK_COLORS[0]
      const series = chart.addSeries(HistogramSeries, {
        color,
        priceLineVisible: false,
        base: 0,
      })
      series.setData(
        dailyData.map((d, dayIdx) => ({
          time: d.date,
          value: posCum[dayIdx][i],
        }))
      )
    }

    // Draw negative stack: outermost first (i = N-1 -> 0)
    for (let i = sortedSymbols.length - 1; i >= 0; i--) {
      const sym = sortedSymbols[i]
      const color = symbolColorMap.get(sym) ?? STACK_COLORS[0]
      const series = chart.addSeries(HistogramSeries, {
        color,
        priceLineVisible: false,
        base: 0,
      })
      series.setData(
        dailyData.map((d, dayIdx) => ({
          time: d.date,
          value: negCum[dayIdx][i],
        }))
      )
    }

    // Crosshair
    chart.subscribeCrosshairMove((param) => {
      if (param.time) {
        const key = String(param.time)
        const deltas = deltasByTime.current.get(key)
        if (deltas) {
          const total = Object.values(deltas).reduce((s, v) => s + v, 0)
          setHoverData({ date: key, deltas, total })
        }
      } else {
        setHoverData(null)
      }
    })

    chart.timeScale().fitContent()
    chartRef.current = chart

    return startLifecycle([chart])
  }, [data, sortedSymbols, symbolColorMap, startLifecycle])

  // Default to latest day
  const latestDeltas = useMemo(() => {
    if (data.length < 2 || !sortedSymbols.length) return null
    const last = data[data.length - 1]
    const prev = data[data.length - 2]
    const deltas: Record<string, number> = {}
    for (const sym of sortedSymbols) {
      deltas[sym] = (last.breakdown[sym] ?? 0) - (prev.breakdown[sym] ?? 0)
    }
    const total = Object.values(deltas).reduce((s, v) => s + v, 0)
    return { date: last.date, deltas, total }
  }, [data, sortedSymbols])
  const displayData = hoverData ?? latestDeltas

  return (
    <div className="space-y-2">
      <h3 className="text-sm font-semibold px-1">Daily Contribution</h3>
      <div ref={ref} className="w-full rounded-md overflow-hidden" />
      <SymbolLegend
        sortedSymbols={sortedSymbols}
        symbolColorMap={symbolColorMap}
        values={displayData ? sortedSymbols.map((sym) => {
          const v = displayData.deltas[sym]
          return v !== undefined ? `${v >= 0 ? "+" : ""}${v.toFixed(2)}` : undefined
        }) : undefined}
        valueColors={displayData ? sortedSymbols.map((sym) => {
          const v = displayData.deltas[sym]
          return v !== undefined ? (v >= 0 ? "text-emerald-500" : "text-red-500") : undefined
        }) : undefined}
        suffix={displayData ? (
          <span className="text-xs font-medium ml-auto">
            Net: <span className={displayData.total >= 0 ? "text-emerald-500" : "text-red-500"}>
              {displayData.total >= 0 ? "+" : ""}{displayData.total.toFixed(2)}
            </span>
          </span>
        ) : undefined}
      />
    </div>
  )
}
