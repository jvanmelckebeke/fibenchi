import { useState, useEffect, useRef, useMemo } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, UserPlus, X, Plus, Loader2 } from "lucide-react"
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
          <StackedAreaChart data={performance} baseValue={etf.base_value} />
          <PerformanceStats data={performance} baseValue={etf.base_value} />
        </>
      )}

      {performance && performance.length === 0 && (
        <p className="text-muted-foreground">
          No performance data. Make sure constituent stocks have price history from {etf.base_date}.
        </p>
      )}

      <HoldingsTable etfId={etfId} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ThesisSection etfId={etfId} />
        <AnnotationsSection etfId={etfId} />
      </div>
    </div>
  )
}

function StackedAreaChart({
  data,
  baseValue,
}: {
  data: PerformanceBreakdownPoint[]
  baseValue: number
}) {
  const ref = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const topSeriesRef = useRef<ReturnType<IChartApi["addSeries"]> | null>(null)
  const [hoverData, setHoverData] = useState<{ total: number; breakdown: Record<string, number> } | null>(null)

  // Lookup maps for crosshair snap
  const totalByTime = useRef(new Map<string, number>())
  const breakdownByTime = useRef(new Map<string, Record<string, number>>())

  // Sort symbols by average contribution (largest first = bottom of stack)
  const sortedSymbols = useMemo(() => {
    const avgMap = new Map<string, number>()
    for (const point of data) {
      for (const [sym, val] of Object.entries(point.breakdown)) {
        avgMap.set(sym, (avgMap.get(sym) ?? 0) + val)
      }
    }
    // Sort descending by total contribution — largest at bottom
    return [...avgMap.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([sym]) => sym)
  }, [data])

  const symbolColorMap = useMemo(() => {
    const map = new Map<string, string>()
    sortedSymbols.forEach((sym, i) => {
      map.set(sym, STACK_COLORS[i % STACK_COLORS.length])
    })
    return map
  }, [sortedSymbols])

  useEffect(() => {
    if (!ref.current || !data.length || !sortedSymbols.length) return

    // Build lookup maps
    totalByTime.current.clear()
    breakdownByTime.current.clear()
    for (const point of data) {
      totalByTime.current.set(point.date, point.value)
      breakdownByTime.current.set(point.date, point.breakdown)
    }

    const dark = document.documentElement.classList.contains("dark")

    const chart = createChart(ref.current, {
      width: ref.current.clientWidth,
      height: 440,
      layout: {
        background: { type: ColorType.Solid, color: dark ? "#18181b" : "#ffffff" },
        textColor: dark ? "#a1a1aa" : "#71717a",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: dark ? "#27272a" : "#f4f4f5" },
        horzLines: { color: dark ? "#27272a" : "#f4f4f5" },
      },
      rightPriceScale: { borderColor: dark ? "#3f3f46" : "#e4e4e7" },
      timeScale: { borderColor: dark ? "#3f3f46" : "#e4e4e7", timeVisible: false },
      crosshair: { mode: 0 },
    })

    // Build cumulative series: for position i, value = sum of symbols 0..i
    // Draw from top (highest cumulative) to bottom (lowest) so each area covers those below
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

    // Draw top-to-bottom (highest cumulative first)
    let topSeries: ReturnType<IChartApi["addSeries"]> | null = null
    for (let idx = 0; idx < cumulativeData.length; idx++) {
      const { symbol, points } = cumulativeData[idx]
      const color = symbolColorMap.get(symbol) ?? STACK_COLORS[0]
      const isTop = idx === 0 // topmost series = total value
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
    const baseLine = chart.addSeries(LineSeries, {
      color: dark ? "rgba(161, 161, 170, 0.5)" : "rgba(113, 113, 122, 0.5)",
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

        // Snap crosshair to the total-value series
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

  // Show hover values or latest values as default
  const lastPoint = data[data.length - 1]
  const displayData = hoverData ?? (lastPoint ? { total: lastPoint.value, breakdown: lastPoint.breakdown } : null)

  return (
    <div className="space-y-2">
      <div ref={ref} className="w-full rounded-md overflow-hidden" />
      <div className="flex flex-wrap gap-x-4 gap-y-1 px-1 items-center">
        {sortedSymbols.map((sym) => {
          const val = displayData?.breakdown[sym]
          return (
            <div key={sym} className="flex items-center gap-1.5 text-xs">
              <div
                className="w-3 h-3 rounded-sm flex-shrink-0"
                style={{ backgroundColor: symbolColorMap.get(sym) }}
              />
              <Link to={`/asset/${sym}`} className="hover:underline text-muted-foreground hover:text-foreground">
                {sym}
              </Link>
              {val !== undefined && (
                <span className="font-mono text-muted-foreground">{val.toFixed(2)}</span>
              )}
            </div>
          )
        })}
        {displayData && (
          <div className="flex items-center gap-1.5 text-xs font-medium ml-auto">
            Total: {displayData.total.toFixed(2)}
          </div>
        )}
      </div>
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
              <div className="grid grid-cols-[4rem_1fr_3.5rem_4rem_4rem_3.5rem_3.5rem_4rem_3.5rem_2rem] text-xs text-muted-foreground border-b border-border pb-1 mb-1 gap-x-2">
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
                  <div key={asset.id} className="grid grid-cols-[4rem_1fr_3.5rem_4rem_4rem_3.5rem_3.5rem_4rem_3.5rem_2rem] text-sm py-1 hover:bg-muted/50 rounded gap-x-2 items-center group/row">
                    <Link to={`/asset/${asset.symbol}`} className="font-mono text-xs text-primary hover:underline">
                      {asset.symbol}
                    </Link>
                    <span className="text-muted-foreground truncate text-xs">{ind?.name ?? asset.name}</span>
                    <IndicatorCell value={ind?.weight_pct != null ? `${ind.weight_pct.toFixed(1)}%` : null} />
                    {indicatorsLoading ? (
                      <span className="col-span-6 text-right text-xs text-muted-foreground animate-pulse">Loading...</span>
                    ) : (
                      <>
                        <IndicatorCell value={ind?.close != null ? ind.close.toFixed(0) : null} />
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
