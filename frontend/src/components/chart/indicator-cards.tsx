import { useState, useEffect, useRef, useCallback } from "react"
import type { IChartApi } from "lightweight-charts"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  resolveThresholdColor,
  getNumericValue,
  type IndicatorDescriptor,
} from "@/lib/indicator-registry"
import { useChartHoverValues, useChartData } from "./chart-sync-provider"
import { createSubChart, setSubChartData, type SubChartState } from "./chart-builders"
import { SubChartLegend } from "./chart-legends"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"

// ---------------------------------------------------------------------------
// Card helper text
// ---------------------------------------------------------------------------

const CARD_HELP: Record<string, string> = {
  atr: "Average price range per day — higher means more volatile",
  adx: "Trend strength — above 25 is a strong trend",
}

// ---------------------------------------------------------------------------
// Card value display
// ---------------------------------------------------------------------------

function CardValue({
  descriptor,
  values,
}: {
  descriptor: IndicatorDescriptor
  values: Record<string, number | undefined>
}) {
  const mainSeries = descriptor.series[0]
  const mainVal = getNumericValue(values as Record<string, number | null>, mainSeries.field)

  if (mainVal == null) {
    return <span className="text-2xl font-semibold tabular-nums text-muted-foreground">--</span>
  }

  const colorClass = resolveThresholdColor(mainSeries.thresholdColors, mainVal)

  return (
    <div className="flex flex-col">
      <span className={`text-2xl font-semibold tabular-nums ${colorClass || "text-foreground"}`}>
        {mainVal.toFixed(descriptor.decimals)}
      </span>
      {/* ADX: show +DI / -DI below the main value */}
      {descriptor.id === "adx" && (
        <div className="flex gap-3 text-xs tabular-nums mt-0.5">
          <span className="text-emerald-500">
            +DI {getNumericValue(values as Record<string, number | null>, "plus_di")?.toFixed(1) ?? "--"}
          </span>
          <span className="text-red-500">
            -DI {getNumericValue(values as Record<string, number | null>, "minus_di")?.toFixed(1) ?? "--"}
          </span>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Modal chart (standalone, no crosshair sync)
// ---------------------------------------------------------------------------

function ModalChart({ descriptor }: { descriptor: IndicatorDescriptor }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const stateRef = useRef<SubChartState | null>(null)
  const { indicators } = useChartData()
  const { startLifecycle } = useChartLifecycle(containerRef, [chartRef])

  useEffect(() => {
    if (!containerRef.current) return

    const state = createSubChart(containerRef.current, descriptor, 250)
    chartRef.current = state.chart
    stateRef.current = state

    const cleanupLifecycle = startLifecycle([state.chart])

    return () => {
      stateRef.current = null
      chartRef.current = null
      cleanupLifecycle()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- structural deps only
  }, [descriptor.id, startLifecycle])

  useEffect(() => {
    const state = stateRef.current
    if (!state || !indicators.length) return

    setSubChartData(state, indicators)
    state.chart.timeScale().fitContent()
  }, [indicators, descriptor.id])

  return <div ref={containerRef} className="w-full rounded-md overflow-hidden" />
}

// ---------------------------------------------------------------------------
// Indicator Cards
// ---------------------------------------------------------------------------

interface IndicatorCardsProps {
  descriptors: IndicatorDescriptor[]
}

export function IndicatorCards({ descriptors }: IndicatorCardsProps) {
  const { hoverValues, latestValues } = useChartHoverValues()
  const [openDescriptor, setOpenDescriptor] = useState<IndicatorDescriptor | null>(null)

  const values = hoverValues?.indicators ?? latestValues.indicators

  const handleOpenChange = useCallback((open: boolean) => {
    if (!open) setOpenDescriptor(null)
  }, [])

  if (descriptors.length === 0) return null

  return (
    <>
      <div className="grid grid-cols-2 gap-2 mt-2">
        {descriptors.map((desc) => (
          <button
            key={desc.id}
            type="button"
            onClick={() => setOpenDescriptor(desc)}
            className="ring-foreground/10 bg-card text-card-foreground rounded-xl px-4 py-3 ring-1 shadow-xs hover:ring-2 hover:ring-foreground/40 transition-shadow cursor-pointer flex items-center justify-between gap-3 text-left"
          >
            <div className="flex flex-col gap-0.5">
              <span className="text-sm font-medium">{desc.shortLabel}</span>
              {CARD_HELP[desc.id] && (
                <span className="text-[11px] leading-tight text-muted-foreground">{CARD_HELP[desc.id]}</span>
              )}
            </div>
            <CardValue descriptor={desc} values={values} />
          </button>
        ))}
      </div>

      <Dialog open={openDescriptor !== null} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{openDescriptor?.label}</DialogTitle>
          </DialogHeader>
          {openDescriptor && (
            <div className="flex flex-col gap-1">
              <SubChartLegend
                descriptorId={openDescriptor.id}
                values={null}
                latest={latestValues}
              />
              <ModalChart descriptor={openDescriptor} />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
