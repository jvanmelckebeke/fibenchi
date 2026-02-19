import { useState, useEffect, useRef, useMemo } from "react"
import { Link } from "react-router-dom"
import {
  createChart,
  type IChartApi,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts"
import { baseChartOptions, STACK_COLORS } from "@/lib/chart-utils"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"
import type { PerformanceBreakdownPoint } from "@/lib/api"

interface SharedChartProps {
  data: PerformanceBreakdownPoint[]
  sortedSymbols: string[]
  symbolColorMap: Map<string, string>
}

/**
 * Rebases each symbol's contribution to start at baseValue, then renders
 * individual line series so relative performance is easy to compare.
 */
export function PerformanceOverlayChart({
  data,
  baseValue,
  sortedSymbols,
  symbolColorMap,
}: SharedChartProps & { baseValue: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const totalSeriesRef = useRef<ReturnType<IChartApi["addSeries"]> | null>(null)
  const baseLineRef = useRef<ReturnType<IChartApi["addSeries"]> | null>(null)
  const [hoverData, setHoverData] = useState<{
    total: number
    rebased: Record<string, number>
  } | null>(null)
  const { theme, startLifecycle } = useChartLifecycle(ref, [chartRef])

  // Lookup maps for crosshair
  const totalByTime = useRef(new Map<string, number>())
  const rebasedByTime = useRef(new Map<string, Record<string, number>>())

  useEffect(() => {
    if (!ref.current || !data.length || !sortedSymbols.length) return

    const firstBreakdown = data[0].breakdown

    // Pre-compute rebased values: contribution[sym][date] / contribution[sym][first_date] * baseValue
    // Symbols with a zero first-date contribution get a flat baseValue line.
    totalByTime.current.clear()
    rebasedByTime.current.clear()

    const rebasedSeries = new Map<string, { time: string; value: number }[]>()
    for (const sym of sortedSymbols) {
      rebasedSeries.set(sym, [])
    }

    for (const point of data) {
      totalByTime.current.set(point.date, point.value)
      const rebasedRow: Record<string, number> = {}
      for (const sym of sortedSymbols) {
        const firstVal = firstBreakdown[sym] ?? 0
        const curVal = point.breakdown[sym] ?? 0
        const rebased = firstVal !== 0 ? (curVal / firstVal) * baseValue : baseValue
        rebasedRow[sym] = rebased
        rebasedSeries.get(sym)!.push({ time: point.date, value: rebased })
      }
      rebasedByTime.current.set(point.date, rebasedRow)
    }

    const chart = createChart(ref.current, baseChartOptions(ref.current, 440))

    // Total index line (prominent, white/dark foreground)
    const totalColor = theme.dark ? "rgba(250, 250, 250, 0.85)" : "rgba(24, 24, 27, 0.85)"
    const totalSeries = chart.addSeries(LineSeries, {
      color: totalColor,
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: true,
      lastValueVisible: false,
    })
    totalSeries.setData(data.map((p) => ({ time: p.date, value: p.value })))
    totalSeriesRef.current = totalSeries

    // Per-symbol rebased lines
    for (const sym of sortedSymbols) {
      const color = symbolColorMap.get(sym) ?? STACK_COLORS[0]
      const series = chart.addSeries(LineSeries, {
        color,
        lineWidth: 1,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
        lastValueVisible: false,
      })
      series.setData(rebasedSeries.get(sym)!)
    }

    // Dashed base value reference line
    const baseLine = chart.addSeries(LineSeries, {
      color: theme.dark ? "rgba(161, 161, 170, 0.5)" : "rgba(113, 113, 122, 0.5)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
      lastValueVisible: false,
    })
    baseLine.setData(data.map((p) => ({ time: p.date, value: baseValue })))
    baseLineRef.current = baseLine

    // Crosshair: snap to total line, update legend with per-symbol rebased values
    let snapping = false
    chart.subscribeCrosshairMove((param) => {
      if (param.time) {
        const key = String(param.time)
        const total = totalByTime.current.get(key)
        const rebased = rebasedByTime.current.get(key)
        if (total !== undefined && rebased) {
          setHoverData({ total, rebased })
        }
        if (!snapping && total !== undefined) {
          snapping = true
          chart.setCrosshairPosition(total, param.time, totalSeries)
          snapping = false
        }
      } else {
        setHoverData(null)
      }
    })

    chart.timeScale().fitContent()
    chartRef.current = chart

    const cleanup = startLifecycle([chart])
    return () => {
      cleanup()
      totalSeriesRef.current = null
      baseLineRef.current = null
    }
  }, [data, baseValue, sortedSymbols, symbolColorMap, startLifecycle, theme.dark])

  // Apply baseLine + totalLine theme colors on theme change
  useEffect(() => {
    baseLineRef.current?.applyOptions({
      color: theme.dark ? "rgba(161, 161, 170, 0.5)" : "rgba(113, 113, 122, 0.5)",
    })
    totalSeriesRef.current?.applyOptions({
      color: theme.dark ? "rgba(250, 250, 250, 0.85)" : "rgba(24, 24, 27, 0.85)",
    })
  }, [theme])

  // Default display: last point's data
  const lastRebased = useMemo(() => {
    if (!data.length || !sortedSymbols.length) return null
    const firstBreakdown = data[0].breakdown
    const last = data[data.length - 1]
    const rebased: Record<string, number> = {}
    for (const sym of sortedSymbols) {
      const firstVal = firstBreakdown[sym] ?? 0
      const curVal = last.breakdown[sym] ?? 0
      rebased[sym] = firstVal !== 0 ? (curVal / firstVal) * baseValue : baseValue
    }
    return { total: last.value, rebased }
  }, [data, sortedSymbols, baseValue])

  const displayData = hoverData ?? lastRebased

  return (
    <div className="space-y-2">
      <div ref={ref} className="w-full rounded-md overflow-hidden" />
      <SymbolLegend
        sortedSymbols={sortedSymbols}
        symbolColorMap={symbolColorMap}
        values={displayData ? sortedSymbols.map((sym) => displayData.rebased[sym]?.toFixed(2)) : undefined}
        suffix={displayData ? <span className="text-xs font-medium ml-auto">Index: {displayData.total.toFixed(2)}</span> : undefined}
      />
    </div>
  )
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
