import { useState, useEffect, useRef } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, UserPlus, X, Plus } from "lucide-react"
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
  LineSeries,
} from "lightweight-charts"
import {
  usePseudoEtf,
  usePseudoEtfPerformance,
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

      {isLoading && <p className="text-muted-foreground">Calculating performance...</p>}

      {performance && performance.length > 0 && (
        <>
          <PerformanceChart data={performance} baseValue={etf.base_value} />
          <PerformanceStats data={performance} baseValue={etf.base_value} />
        </>
      )}

      {performance && performance.length === 0 && (
        <p className="text-muted-foreground">
          No performance data. Make sure constituent stocks have price history from {etf.base_date}.
        </p>
      )}

      <Holdings etfId={etfId} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ThesisSection etfId={etfId} />
        <AnnotationsSection etfId={etfId} />
      </div>
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
      crosshair: { mode: 0 },
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

  return <div ref={ref} className="w-full rounded-md overflow-hidden" />
}

function PerformanceStats({ data, baseValue }: { data: { date: string; value: number }[]; baseValue: number }) {
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

function Holdings({ etfId }: { etfId: number }) {
  const { data: etf } = usePseudoEtf(etfId)
  const removeConstituent = useRemovePseudoEtfConstituent()
  const [addingAsset, setAddingAsset] = useState(false)

  if (!etf) return null

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

        <div className="flex flex-wrap gap-2">
          {etf.constituents.map((asset) => (
            <div key={asset.id} className="flex items-center gap-1 group/asset">
              <Link to={`/asset/${asset.symbol}`}>
                <Badge variant="secondary" className="cursor-pointer hover:bg-primary hover:text-primary-foreground transition-colors">
                  {asset.symbol}
                </Badge>
              </Link>
              <Button
                variant="ghost"
                size="icon"
                className="h-5 w-5 opacity-0 group-hover/asset:opacity-100 transition-opacity"
                onClick={() => removeConstituent.mutate({ etfId, assetId: asset.id })}
              >
                <X className="h-3 w-3" />
              </Button>
            </div>
          ))}
        </div>
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
