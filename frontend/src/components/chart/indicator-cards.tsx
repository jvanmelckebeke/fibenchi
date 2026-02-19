import { useState, useEffect, useRef, useCallback } from "react"
import type { LegendValues } from "./chart-legends"
import type { IChartApi } from "lightweight-charts"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { type IndicatorDescriptor } from "@/lib/indicator-registry"
import { IndicatorValue } from "@/components/indicator-value"
import { useChartHoverValues, useChartData } from "./chart-sync-provider"
import { createSubChart, setSubChartData, type SubChartState } from "./chart-builders"
import { SubChartLegend } from "./chart-legends"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"

// ---------------------------------------------------------------------------
// Card helper text
// ---------------------------------------------------------------------------

const CARD_HELP: Record<string, string> = {
  rsi: "Momentum oscillator — below 30 is oversold, above 70 is overbought",
  macd: "Momentum crossover — positive histogram is bullish, negative is bearish",
  atr: "Average daily high-to-low range — higher means more volatile",
  adx: "Trend strength & direction — green is bullish, red is bearish",
}

// ---------------------------------------------------------------------------
// Modal chart (standalone, no crosshair sync)
// ---------------------------------------------------------------------------

function ModalChart({
  descriptor,
  latestValues,
}: {
  descriptor: IndicatorDescriptor
  latestValues: LegendValues
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const stateRef = useRef<SubChartState | null>(null)
  const { indicators } = useChartData()
  const { startLifecycle } = useChartLifecycle(containerRef, [chartRef])
  const [hoverValues, setHoverValues] = useState<LegendValues | null>(null)

  // Build a time → indicator values lookup from the indicators array
  const indicatorsByTime = useRef(new Map<string, Record<string, number>>())
  useEffect(() => {
    indicatorsByTime.current.clear()
    for (const i of indicators) {
      const vals: Record<string, number> = {}
      for (const [field, value] of Object.entries(i.values)) {
        if (value != null && typeof value === "number") vals[field] = value
      }
      indicatorsByTime.current.set(i.date, vals)
    }
  }, [indicators])

  useEffect(() => {
    if (!containerRef.current) return

    const state = createSubChart(containerRef.current, descriptor, 250)
    chartRef.current = state.chart
    stateRef.current = state

    // Subscribe to crosshair moves for legend updates + y-axis snap
    const snapSeries = state.seriesMap.values().next().value
    const handler: Parameters<IChartApi["subscribeCrosshairMove"]>[0] = (param) => {
      if (param.time) {
        const key = String(param.time)
        const vals = indicatorsByTime.current.get(key) ?? {}
        setHoverValues({ indicators: vals })
        // Snap crosshair y-position to the primary series value
        if (snapSeries) {
          const snapVal = vals[state.snapField]
          if (snapVal !== undefined) {
            state.chart.setCrosshairPosition(snapVal, param.time, snapSeries)
          }
        }
      } else {
        setHoverValues(null)
      }
    }
    state.chart.subscribeCrosshairMove(handler)

    const cleanupLifecycle = startLifecycle([state.chart])

    return () => {
      state.chart.unsubscribeCrosshairMove(handler)
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

  return (
    <div className="flex flex-col gap-1">
      <SubChartLegend
        descriptorId={descriptor.id}
        values={hoverValues}
        latest={latestValues}
      />
      <div ref={containerRef} className="w-full rounded-md overflow-hidden" />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Indicator Cards
// ---------------------------------------------------------------------------

interface IndicatorCardsProps {
  descriptors: IndicatorDescriptor[]
  currency?: string
  /** Compact style for inline use (e.g. expanded holdings row). */
  compact?: boolean
}

export function IndicatorCards({ descriptors, currency, compact }: IndicatorCardsProps) {
  const { hoverValues, latestValues } = useChartHoverValues()
  const [openDescriptor, setOpenDescriptor] = useState<IndicatorDescriptor | null>(null)

  const values = hoverValues?.indicators ?? latestValues.indicators

  const handleOpenChange = useCallback((open: boolean) => {
    if (!open) setOpenDescriptor(null)
  }, [])

  if (descriptors.length === 0) return null

  const gridClass = compact
    ? "grid grid-cols-1 gap-2"
    : "grid grid-cols-2 gap-2 mt-2"

  const cardClass = compact
    ? "ring-foreground/10 bg-card text-card-foreground rounded-md px-3 py-2 ring-1 hover:ring-2 hover:ring-foreground/40 transition-shadow cursor-pointer flex items-center justify-between gap-2 text-left"
    : "ring-foreground/10 bg-card text-card-foreground rounded-xl px-4 py-3 ring-1 shadow-xs hover:ring-2 hover:ring-foreground/40 transition-shadow cursor-pointer flex items-center justify-between gap-3 text-left"

  return (
    <>
      <div className={gridClass}>
        {descriptors.map((desc) => (
          <button
            key={desc.id}
            type="button"
            onClick={() => setOpenDescriptor(desc)}
            className={cardClass}
          >
            <div className="flex flex-col gap-0.5">
              <span className={`font-medium ${compact ? "text-xs" : "text-sm"}`}>{desc.shortLabel}</span>
              {!compact && CARD_HELP[desc.id] && (
                <span className="text-[11px] leading-tight text-muted-foreground">{CARD_HELP[desc.id]}</span>
              )}
            </div>
            <IndicatorValue descriptor={desc} values={values} currency={currency} compact={compact} />
          </button>
        ))}
      </div>

      <Dialog open={openDescriptor !== null} onOpenChange={handleOpenChange}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{openDescriptor?.label}</DialogTitle>
            {openDescriptor && CARD_HELP[openDescriptor.id] && (
              <p className="text-sm text-muted-foreground">{CARD_HELP[openDescriptor.id]}</p>
            )}
          </DialogHeader>
          {openDescriptor && (
            <ModalChart descriptor={openDescriptor} latestValues={latestValues} />
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
