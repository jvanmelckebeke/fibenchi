import { useState, useEffect, useRef, useMemo } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, UserPlus, X, Plus, Loader2 } from "lucide-react"
import { formatPrice } from "@/lib/format"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ThesisEditor } from "@/components/thesis-editor"
import { AnnotationsList } from "@/components/annotations-list"
import {
  createChart,
  type IChartApi,
  ColorType,
  AreaSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts"
import type { PerformanceBreakdownPoint } from "@/lib/api"
import {
  usePseudoEtf,
  usePseudoEtfPerformance,
  usePseudoEtfConstituentsIndicators,
  useAssets,
  useAddPseudoEtfConstituents,
  useRemovePseudoEtfConstituent,
  useCreateAsset,
  usePseudoEtfThesis,
  useUpdatePseudoEtfThesis,
  usePseudoEtfAnnotations,
  useCreatePseudoEtfAnnotation,
  useDeletePseudoEtfAnnotation,
} from "@/lib/queries"

const STACK_COLORS = [
  "#2563eb", "#dc2626", "#16a34a", "#d97706", "#9333ea",
  "#0891b2", "#e11d48", "#65a30d", "#c026d3", "#0d9488",
  "#ea580c", "#4f46e5", "#059669", "#db2777", "#ca8a04",
  "#7c3aed", "#0284c7", "#be123c", "#15803d", "#a21caf",
]

function getChartTheme() {
  const dark = document.documentElement.classList.contains("dark")
  return {
    bg: dark ? "#18181b" : "#ffffff",
    text: dark ? "#a1a1aa" : "#71717a",
    grid: dark ? "#27272a" : "#f4f4f5",
    border: dark ? "#3f3f46" : "#e4e4e7",
    dark,
  }
}

function baseChartOptions(container: HTMLElement, height: number) {
  const theme = getChartTheme()
  return {
    width: container.clientWidth,
    height,
    layout: {
      background: { type: ColorType.Solid, color: theme.bg },
      textColor: theme.text,
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: theme.grid },
      horzLines: { color: theme.grid },
    },
    rightPriceScale: { borderColor: theme.border },
    timeScale: { borderColor: theme.border, timeVisible: false },
    crosshair: { mode: 0 as const },
    handleScroll: {
      horzTouchDrag: true,
      vertTouchDrag: false,
      mouseWheel: false,
      pressedMouseMove: true,
    },
    handleScale: {
      mouseWheel: true,
      pinch: true,
      axisPressedMouseMove: false as const,
      axisDoubleClickReset: { time: true, price: false },
    },
  }
}

interface SharedChartProps {
  data: PerformanceBreakdownPoint[]
  sortedSymbols: string[]
  symbolColorMap: Map<string, string>
}

export function PseudoEtfDetailPage() {
  const { id } = useParams<{ id: string }>()
  const etfId = Number(id)
  const { data: etf } = usePseudoEtf(etfId)
  const { data: performance, isLoading } = usePseudoEtfPerformance(etfId)

  const sortedSymbols = useMemo(() => {
    if (!performance?.length) return []
    const avgMap = new Map<string, number>()
    for (const point of performance) {
      for (const [sym, val] of Object.entries(point.breakdown)) {
        avgMap.set(sym, (avgMap.get(sym) ?? 0) + val)
      }
    }
    return [...avgMap.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([sym]) => sym)
  }, [performance])

  const symbolColorMap = useMemo(() => {
    const map = new Map<string, string>()
    sortedSymbols.forEach((sym, i) => {
      map.set(sym, STACK_COLORS[i % STACK_COLORS.length])
    })
    return map
  }, [sortedSymbols])

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

      <div className="text-sm text-muted-foreground">
        Base: {etf.base_date} = {etf.base_value}
      </div>

      {isLoading && (
        <div className="h-[440px] flex flex-col items-center justify-center gap-2 text-muted-foreground">
          <Loader2 className="h-6 w-6 animate-spin" />
          <span className="text-sm">Calculating performance...</span>
        </div>
      )}

      {performance && performance.length > 0 && (
        <>
          <StackedAreaChart data={performance} baseValue={etf.base_value} sortedSymbols={sortedSymbols} symbolColorMap={symbolColorMap} />
          <PerformanceStats data={performance} baseValue={etf.base_value} />
          {performance.length > 1 && (
            <DailyContributionChart data={performance} sortedSymbols={sortedSymbols} symbolColorMap={symbolColorMap} />
          )}
        </>
      )}

      {performance && performance.length === 0 && (
        <p className="text-muted-foreground">
          No performance data. Make sure constituent stocks have price history from {etf.base_date}.
        </p>
      )}

      <HoldingsTable etfId={etfId} />

      <AnnotationsSection etfId={etfId} />
      <ThesisSection etfId={etfId} />
    </div>
  )
}

function StackedAreaChart({
  data,
  baseValue,
  sortedSymbols,
  symbolColorMap,
}: SharedChartProps & { baseValue: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const topSeriesRef = useRef<ReturnType<IChartApi["addSeries"]> | null>(null)
  const [hoverData, setHoverData] = useState<{ total: number; breakdown: Record<string, number> } | null>(null)

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
    }
  }, [data, baseValue, sortedSymbols, symbolColorMap])

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

function DailyContributionChart({ data, sortedSymbols, symbolColorMap }: SharedChartProps) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const [hoverData, setHoverData] = useState<{ date: string; deltas: Record<string, number>; total: number } | null>(null)

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
    // posCum[day][i] = running sum of max(0, delta) for symbols 0..i
    // negCum[day][i] = running sum of min(0, delta) for symbols 0..i
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

    // Draw positive stack: outermost first (i = N-1 → 0)
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

    // Draw negative stack: outermost first (i = N-1 → 0)
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

  // Default to latest day (computed from props, not refs)
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

function PerformanceStats({ data, baseValue }: { data: PerformanceBreakdownPoint[]; baseValue: number }) {
  if (!data.length) return null

  const last = data[data.length - 1]
  const totalReturn = ((last.value - baseValue) / baseValue) * 100

  return (
    <div className="flex gap-6 text-sm">
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

function IndicatorCell({ value, className = "" }: { value: string | null; className?: string }) {
  return (
    <span className={`text-right text-xs ${value === null ? "text-muted-foreground" : className}`}>
      {value ?? "\u2014"}
    </span>
  )
}

function formatChangePct(v: number | null): { text: string | null; className: string } {
  if (v === null) return { text: null, className: "" }
  const sign = v >= 0 ? "+" : ""
  return {
    text: `${sign}${v.toFixed(2)}%`,
    className: v >= 0 ? "text-emerald-500" : "text-red-500",
  }
}

function HoldingsTable({ etfId }: { etfId: number }) {
  const { data: etf } = usePseudoEtf(etfId)
  const { data: indicators, isLoading: indicatorsLoading } = usePseudoEtfConstituentsIndicators(
    etfId,
    (etf?.constituents.length ?? 0) > 0,
  )
  const removeConstituent = useRemovePseudoEtfConstituent()
  const [addingAsset, setAddingAsset] = useState(false)

  if (!etf) return null

  const indicatorMap = new Map((indicators ?? []).map((i) => [i.symbol, i]))

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-base">Holdings ({etf.constituents.length})</CardTitle>
        <Button size="sm" variant="ghost" onClick={() => setAddingAsset(!addingAsset)}>
          <UserPlus className="h-3.5 w-3.5 mr-1" />
          Add
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {addingAsset && (
          <AddConstituentPicker
            etfId={etfId}
            existingIds={etf.constituents.map((a) => a.id)}
            onClose={() => setAddingAsset(false)}
          />
        )}

        {etf.constituents.length === 0 && !addingAsset && (
          <p className="text-sm text-muted-foreground italic">No constituents. Add stocks to this basket.</p>
        )}

        {etf.constituents.length > 0 && (
          <div className="overflow-x-auto">
            <div className="min-w-[750px] space-y-0">
              <div className="grid grid-cols-[4rem_1fr_3.5rem_5rem_4rem_3.5rem_3.5rem_4rem_3.5rem_2rem] text-xs text-muted-foreground border-b border-border pb-1 mb-1 gap-x-2">
                <span>Symbol</span>
                <span>Name</span>
                <span className="text-right">Wt%</span>
                <span className="text-right">Price</span>
                <span className="text-right">Chg%</span>
                <span className="text-right">RSI</span>
                <span className="text-right">SMA20</span>
                <span className="text-right">MACD</span>
                <span className="text-right">BB</span>
                <span></span>
              </div>
              {etf.constituents.map((asset) => {
                const ind = indicatorMap.get(asset.symbol)
                const chg = formatChangePct(ind?.change_pct ?? null)
                const rsiVal = ind?.rsi
                const rsiColor = rsiVal != null ? (rsiVal > 70 ? "text-red-500" : rsiVal < 30 ? "text-emerald-500" : "") : ""
                const smaAbove = ind?.sma_20 != null && ind?.close != null ? ind.close > ind.sma_20 : null
                const macdDir = ind?.macd_signal_dir
                const bbPos = ind?.bb_position

                return (
                  <div key={asset.id} className="grid grid-cols-[4rem_1fr_3.5rem_5rem_4rem_3.5rem_3.5rem_4rem_3.5rem_2rem] text-sm py-1 hover:bg-muted/50 rounded gap-x-2 items-center group/row">
                    <Link to={`/asset/${asset.symbol}`} className="font-mono text-xs text-primary hover:underline">
                      {asset.symbol}
                    </Link>
                    <span className="text-muted-foreground truncate text-xs">{ind?.name ?? asset.name}</span>
                    <IndicatorCell value={ind?.weight_pct != null ? `${ind.weight_pct.toFixed(1)}%` : null} />
                    {indicatorsLoading ? (
                      <span className="col-span-6 text-right text-xs text-muted-foreground animate-pulse">Loading...</span>
                    ) : (
                      <>
                        <IndicatorCell value={ind?.close != null ? formatPrice(ind.close, ind.currency, 0) : null} />
                        <IndicatorCell value={chg.text} className={chg.className} />
                        <IndicatorCell value={rsiVal != null ? rsiVal.toFixed(0) : null} className={rsiColor} />
                        <IndicatorCell
                          value={smaAbove !== null ? (smaAbove ? "Above" : "Below") : null}
                          className={smaAbove === true ? "text-emerald-500" : smaAbove === false ? "text-red-500" : ""}
                        />
                        <IndicatorCell
                          value={macdDir != null ? (macdDir === "bullish" ? "Bull" : "Bear") : null}
                          className={macdDir === "bullish" ? "text-emerald-500" : macdDir === "bearish" ? "text-red-500" : ""}
                        />
                        <IndicatorCell
                          value={bbPos != null ? bbPos.charAt(0).toUpperCase() + bbPos.slice(1) : null}
                          className={bbPos === "above" ? "text-red-500" : bbPos === "below" ? "text-emerald-500" : ""}
                        />
                      </>
                    )}
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-5 w-5 opacity-0 group-hover/row:opacity-100 transition-opacity"
                      onClick={() => removeConstituent.mutate({ etfId, assetId: asset.id })}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function AddConstituentPicker({
  etfId,
  existingIds,
  onClose,
}: {
  etfId: number
  existingIds: number[]
  onClose: () => void
}) {
  const { data: allAssets } = useAssets()
  const addConstituents = useAddPseudoEtfConstituents()
  const createAsset = useCreateAsset()
  const available = allAssets?.filter((a) => !existingIds.includes(a.id)) ?? []
  const [selected, setSelected] = useState<number[]>([])
  const [newTicker, setNewTicker] = useState("")
  const [tickerError, setTickerError] = useState("")

  const toggle = (id: number) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const handleAdd = () => {
    if (!selected.length) return
    addConstituents.mutate({ etfId, assetIds: selected }, { onSuccess: () => onClose() })
  }

  const handleNewTicker = () => {
    const sym = newTicker.trim().toUpperCase()
    if (!sym) return
    setTickerError("")
    createAsset.mutate(
      { symbol: sym, watchlisted: false },
      {
        onSuccess: (asset) => {
          addConstituents.mutate(
            { etfId, assetIds: [asset.id] },
            { onSuccess: () => { setNewTicker(""); onClose() } }
          )
        },
        onError: (err) => setTickerError(err.message),
      }
    )
  }

  return (
    <div className="p-3 rounded-md border bg-muted/30 space-y-3">
      <div className="flex gap-2 items-center">
        <Input
          placeholder="New ticker (e.g. AAPL)"
          value={newTicker}
          onChange={(e) => { setNewTicker(e.target.value); setTickerError("") }}
          onKeyDown={(e) => e.key === "Enter" && handleNewTicker()}
          className="w-48"
        />
        <Button size="sm" onClick={handleNewTicker} disabled={!newTicker.trim() || createAsset.isPending}>
          <Plus className="h-3.5 w-3.5 mr-1" />
          {createAsset.isPending ? "Adding..." : "Add new"}
        </Button>
        {tickerError && <span className="text-xs text-destructive">{tickerError}</span>}
      </div>

      {available.length > 0 && (
        <>
          <p className="text-xs text-muted-foreground">Or pick existing assets:</p>
          <div className="flex flex-wrap gap-1.5">
            {available.map((a) => (
              <Badge
                key={a.id}
                variant={selected.includes(a.id) ? "default" : "outline"}
                className="cursor-pointer"
                onClick={() => toggle(a.id)}
              >
                {a.symbol}
              </Badge>
            ))}
          </div>
        </>
      )}

      <div className="flex justify-end gap-1">
        <Button size="sm" variant="ghost" onClick={onClose}>Cancel</Button>
        {selected.length > 0 && (
          <Button size="sm" onClick={handleAdd} disabled={addConstituents.isPending}>
            Add ({selected.length})
          </Button>
        )}
      </div>
    </div>
  )
}

function ThesisSection({ etfId }: { etfId: number }) {
  const { data: thesis } = usePseudoEtfThesis(etfId)
  const updateThesis = useUpdatePseudoEtfThesis(etfId)

  return (
    <ThesisEditor
      thesis={thesis}
      onSave={(content) => updateThesis.mutate(content)}
      isSaving={updateThesis.isPending}
    />
  )
}

function AnnotationsSection({ etfId }: { etfId: number }) {
  const { data: annotations } = usePseudoEtfAnnotations(etfId)
  const createAnnotation = useCreatePseudoEtfAnnotation(etfId)
  const deleteAnnotation = useDeletePseudoEtfAnnotation(etfId)

  return (
    <AnnotationsList
      annotations={annotations}
      onCreate={(data) => createAnnotation.mutate(data)}
      onDelete={(id) => deleteAnnotation.mutate(id)}
      isCreating={createAnnotation.isPending}
    />
  )
}
