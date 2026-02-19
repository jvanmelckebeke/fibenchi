import { useEffect, useRef, useCallback, useMemo, Fragment } from "react"
import type { IChartApi } from "lightweight-charts"
import type { Annotation } from "@/lib/api"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"
import {
  createMainChart,
  createOverlays,
  setMainSeriesData,
  setAllOverlayData,
  addAnnotationMarkers,
  type OverlayState,
  type MarkersHandle,
} from "./chart-builders"
import { Legend } from "./chart-legends"
import { useRegisterChart, useChartHoverValues, useChartData } from "./chart-sync-provider"
import { getOverlayDescriptors, isIndicatorVisible } from "@/lib/indicator-registry"

interface CandlestickChartProps {
  annotations: Annotation[]
  /** Per-descriptor visibility (keys = descriptor IDs). Missing keys default to true. */
  indicatorVisibility?: Record<string, boolean>
  chartType?: "candle" | "line"
  height?: number
  /** Whether to hide the time axis (e.g. when sub-charts are stacked below). */
  hideTimeAxis?: boolean
  /** Whether to show the OHLC + overlay legend above the chart. */
  showLegend?: boolean
  /** Rounded corner class for the chart container. */
  roundedClass?: string
  /** Called with the chart API after creation (for external lifecycle management). */
  onChartReady?: (chart: IChartApi) => void
  /** Called when the chart is destroyed. */
  onChartDestroy?: () => void
}

interface ChartState {
  mainChart: IChartApi
  mainSeries: ReturnType<IChartApi["addSeries"]>
  overlays: OverlayState
}

export function CandlestickChart({
  annotations,
  indicatorVisibility,
  chartType = "candle",
  height = 400,
  hideTimeAxis = false,
  showLegend = true,
  roundedClass = "rounded-md",
  onChartReady,
  onChartDestroy,
}: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const chartStateRef = useRef<ChartState | null>(null)
  const markersRef = useRef<MarkersHandle | null>(null)

  const { startLifecycle } = useChartLifecycle(containerRef, [chartRef])
  const register = useRegisterChart()
  const { hoverValues, latestValues } = useChartHoverValues()
  const { prices, indicators } = useChartData()

  const isVisible = useCallback(
    (id: string) => isIndicatorVisible(indicatorVisibility, id),
    [indicatorVisibility],
  )

  const enabledOverlayIds = useMemo(() => {
    const ids = new Set<string>()
    for (const d of getOverlayDescriptors()) {
      if (isVisible(d.id)) ids.add(d.id)
    }
    return ids
  }, [isVisible])

  // Effect 1: Create chart structure
  useEffect(() => {
    if (!containerRef.current) return

    const { chart, series } = createMainChart(containerRef.current, chartType, height, hideTimeAxis)
    const overlays = createOverlays(chart)

    chartRef.current = chart
    chartStateRef.current = { mainChart: chart, mainSeries: series, overlays }

    onChartReady?.(chart)

    const unregister = register({ chart, series, role: "main" })
    const cleanupLifecycle = startLifecycle([chart])

    return () => {
      markersRef.current = null
      chartStateRef.current = null
      chartRef.current = null
      onChartDestroy?.()
      unregister()
      cleanupLifecycle()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- structural dependencies only
  }, [chartType, height, hideTimeAxis, register, startLifecycle])

  // Effect 2: Update data in-place
  useEffect(() => {
    const state = chartStateRef.current
    if (!state || !prices.length) return

    setMainSeriesData(state.mainSeries, prices, chartType)
    setAllOverlayData(state.overlays, indicators, enabledOverlayIds)

    try {
      markersRef.current?.detach()
    } catch {
      /* chart may have been recreated */
    }
    markersRef.current = addAnnotationMarkers(state.mainSeries, annotations)

    state.mainChart.timeScale().fitContent()
  }, [prices, indicators, annotations, enabledOverlayIds, chartType, height])

  const resetView = useCallback(() => {
    chartRef.current?.timeScale().fitContent()
  }, [])

  return (
    <Fragment>
      {showLegend && (
        <div className="flex items-center justify-between px-1 py-1">
          <Legend values={hoverValues} latest={latestValues} />
          <button
            onClick={resetView}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
            title="Reset chart view"
          >
            Reset view
          </button>
        </div>
      )}
      <div ref={containerRef} className={`w-full ${roundedClass} overflow-hidden`} />
    </Fragment>
  )
}
