import { useState, useEffect, useRef, useMemo } from "react"
import {
  createChart,
  type IChartApi,
  LineSeries,
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
