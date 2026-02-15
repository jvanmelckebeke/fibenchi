import { useState, useEffect, useRef, useMemo } from "react"
import { Link } from "react-router-dom"
import {
  createChart,
  type IChartApi,
  AreaSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts"
import { baseChartOptions, getChartTheme, useChartTheme, chartThemeOptions, STACK_COLORS } from "@/lib/chart-utils"
import type { PerformanceBreakdownPoint } from "@/lib/api"

interface SharedChartProps {
  data: PerformanceBreakdownPoint[]
  sortedSymbols: string[]
  symbolColorMap: Map<string, string>
}

export function StackedAreaChart({
  data,
  baseValue,
  sortedSymbols,
  symbolColorMap,
}: SharedChartProps & { baseValue: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const topSeriesRef = useRef<ReturnType<IChartApi["addSeries"]> | null>(null)
  const baseLineRef = useRef<ReturnType<IChartApi["addSeries"]> | null>(null)
  const [hoverData, setHoverData] = useState<{ total: number; breakdown: Record<string, number> } | null>(null)
  const theme = useChartTheme()

  const totalByTime = useRef(new Map<string, number>())
  const breakdownByTime = useRef(new Map<string, Record<string, number>>())

  useEffect(() => {
    if (!ref.current || !data.length || !sortedSymbols.length) return

    totalByTime.current.clear()
    breakdownByTime.current.clear()
    for (const point of data) {
      totalByTime.current.set(point.date, point.value)
      breakdownByTime.current.set(point.date, point.breakdown)
    }

    const chart = createChart(ref.current, baseChartOptions(ref.current, 440))

    // Build cumulative series: for position i, value = sum of symbols 0..i
    const cumulativeData: { symbol: string; points: { time: string; value: number }[] }[] = []

    for (let i = sortedSymbols.length - 1; i >= 0; i--) {
      const points = data.map((point) => {
        let cumValue = 0
        for (let j = 0; j <= i; j++) {
          cumValue += point.breakdown[sortedSymbols[j]] ?? 0
        }
        return { time: point.date, value: cumValue }
      })
      cumulativeData.push({ symbol: sortedSymbols[i], points })
    }

    let topSeries: ReturnType<IChartApi["addSeries"]> | null = null
    for (let idx = 0; idx < cumulativeData.length; idx++) {
      const { symbol, points } = cumulativeData[idx]
      const color = symbolColorMap.get(symbol) ?? STACK_COLORS[0]
      const isTop = idx === 0
      const series = chart.addSeries(AreaSeries, {
        lineColor: color,
        topColor: color,
        bottomColor: color,
        lineWidth: 1,
        priceLineVisible: false,
        crosshairMarkerVisible: isTop,
      })
      series.setData(points)
      if (isTop) topSeries = series
    }
    topSeriesRef.current = topSeries

    // Base value reference line
    const theme = getChartTheme()
    const baseLine = chart.addSeries(LineSeries, {
      color: theme.dark ? "rgba(161, 161, 170, 0.5)" : "rgba(113, 113, 122, 0.5)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })
    baseLine.setData(data.map((p) => ({ time: p.date, value: baseValue })))
    baseLineRef.current = baseLine

    // Crosshair snap + legend update
    let snapping = false
    chart.subscribeCrosshairMove((param) => {
      if (param.time) {
        const key = String(param.time)
        const total = totalByTime.current.get(key)
        const breakdown = breakdownByTime.current.get(key)
        if (total !== undefined && breakdown) {
          setHoverData({ total, breakdown })
        }
        if (!snapping && total !== undefined && topSeries) {
          snapping = true
          chart.setCrosshairPosition(total, param.time, topSeries)
          snapping = false
        }
      } else {
        setHoverData(null)
      }
    })

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
      topSeriesRef.current = null
      baseLineRef.current = null
    }
  }, [data, baseValue, sortedSymbols, symbolColorMap])

  // Apply theme changes without recreating charts
  useEffect(() => {
    chartRef.current?.applyOptions(chartThemeOptions(theme))
    baseLineRef.current?.applyOptions({
      color: theme.dark ? "rgba(161, 161, 170, 0.5)" : "rgba(113, 113, 122, 0.5)",
    })
  }, [theme])

  const lastPoint = data[data.length - 1]
  const displayData = hoverData ?? (lastPoint ? { total: lastPoint.value, breakdown: lastPoint.breakdown } : null)

  return (
    <div className="space-y-2">
      <div ref={ref} className="w-full rounded-md overflow-hidden" />
      <SymbolLegend
        sortedSymbols={sortedSymbols}
        symbolColorMap={symbolColorMap}
        values={displayData ? sortedSymbols.map((sym) => displayData.breakdown[sym]?.toFixed(2)) : undefined}
        suffix={displayData ? <span className="text-xs font-medium ml-auto">Total: {displayData.total.toFixed(2)}</span> : undefined}
      />
    </div>
  )
}

export function DailyContributionChart({ data, sortedSymbols, symbolColorMap }: SharedChartProps) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const [hoverData, setHoverData] = useState<{ date: string; deltas: Record<string, number>; total: number } | null>(null)
  const theme = useChartTheme()

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
  }, [data, sortedSymbols, symbolColorMap])

  // Apply theme changes without recreating charts
  useEffect(() => {
    chartRef.current?.applyOptions(chartThemeOptions(theme))
  }, [theme])

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

function SymbolLegend({
  sortedSymbols,
  symbolColorMap,
  values,
  valueColors,
  suffix,
}: {
  sortedSymbols: string[]
  symbolColorMap: Map<string, string>
  values?: (string | undefined)[]
  valueColors?: (string | undefined)[]
  suffix?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 px-1 items-center">
      {sortedSymbols.map((sym, idx) => (
        <div key={sym} className="flex items-center gap-1.5 text-xs">
          <div
            className="w-3 h-3 rounded-sm flex-shrink-0"
            style={{ backgroundColor: symbolColorMap.get(sym) }}
          />
          <Link to={`/asset/${sym}`} className="hover:underline text-muted-foreground hover:text-foreground">
            {sym}
          </Link>
          {values?.[idx] !== undefined && (
            <span className={`font-mono ${valueColors?.[idx] ?? "text-muted-foreground"}`}>
              {values[idx]}
            </span>
          )}
        </div>
      ))}
      {suffix}
    </div>
  )
}
