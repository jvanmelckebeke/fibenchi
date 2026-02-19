import { useState, useMemo } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, UserPlus, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { ThesisEditor } from "@/components/thesis-editor"
import { AnnotationsList } from "@/components/annotations-list"
import { HoldingsGrid, type HoldingsGridRow } from "@/components/holdings-grid"
import { AddConstituentPicker } from "@/components/add-constituent-picker"
import { CrosshairTimeSyncProvider } from "@/components/chart/crosshair-time-sync"
import {
  PerformanceOverlayChart,
  DailyContributionChart,
} from "@/components/chart/pseudo-etf-charts"
import { STACK_COLORS } from "@/lib/chart-utils"
import { formatChangePct } from "@/lib/format"
import { useSettings } from "@/lib/settings"
import type { PerformanceBreakdownPoint } from "@/lib/api"
import {
  usePseudoEtf,
  usePseudoEtfPerformance,
  usePseudoEtfConstituentsIndicators,
  useRemovePseudoEtfConstituent,
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
          <PerformanceOverlayChart data={performance} baseValue={etf.base_value} sortedSymbols={sortedSymbols} symbolColorMap={symbolColorMap} />
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
      <EtfAnnotations etfId={etfId} />
      <EtfThesis etfId={etfId} />
    </div>
  )
}

function EtfAnnotations({ etfId }: { etfId: number }) {
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

function EtfThesis({ etfId }: { etfId: number }) {
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

function PerformanceStats({ data, baseValue }: { data: PerformanceBreakdownPoint[]; baseValue: number }) {
  if (!data.length) return null

  const last = data[data.length - 1]
  const totalReturn = ((last.value - baseValue) / baseValue) * 100
  const returnFmt = formatChangePct(totalReturn)

  return (
    <div className="flex gap-6 text-sm">
      <div>
        <span className="text-muted-foreground">Current: </span>
        <span className="font-medium">{last.value.toFixed(2)}</span>
      </div>
      <div>
        <span className="text-muted-foreground">Total return: </span>
        <span className={`font-medium ${returnFmt.className}`}>
          {returnFmt.text}
        </span>
      </div>
      <div>
        <span className="text-muted-foreground">Period: </span>
        <span className="font-medium">{data[0].date} to {last.date}</span>
      </div>
    </div>
  )
}

function HoldingsTable({ etfId }: { etfId: number }) {
  const { data: etf } = usePseudoEtf(etfId)
  const { data: indicators, isLoading: indicatorsLoading } = usePseudoEtfConstituentsIndicators(
    etfId,
    (etf?.constituents.length ?? 0) > 0,
  )
  const removeConstituent = useRemovePseudoEtfConstituent()
  const [addingAsset, setAddingAsset] = useState(false)
  const { settings } = useSettings()
  const syncEnabled = settings.sync_pseudo_etf_crosshairs

  if (!etf) return null

  const indicatorMap = new Map((indicators ?? []).map((i) => [i.symbol, i]))

  const rows: HoldingsGridRow[] = etf.constituents.map((a) => {
    const ind = indicatorMap.get(a.symbol)
    return {
      key: a.id,
      symbol: a.symbol,
      name: ind?.name ?? a.name,
      percent: ind?.weight_pct ?? null,
    }
  })

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
          <CrosshairTimeSyncProvider enabled={syncEnabled}>
            <HoldingsGrid
              rows={rows}
              indicatorMap={indicatorMap}
              indicatorsLoading={indicatorsLoading}
              onRemove={(key) => removeConstituent.mutate({ etfId, assetId: key as number })}
            />
          </CrosshairTimeSyncProvider>
        )}
      </CardContent>
    </Card>
  )
}

