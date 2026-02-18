import { useEffect, useRef, useCallback, useMemo, Fragment } from "react"
import type { IChartApi } from "lightweight-charts"
import type { Price, Indicator, Annotation } from "@/lib/api"
import { useChartSync, type ChartEntry } from "@/lib/use-chart-sync"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"
import {
  createMainChart,
  createOverlays,
  createSubChart,
  setMainSeriesData,
  setAllOverlayData,
  setSubChartData,
  addAnnotationMarkers,
  type OverlayState,
  type SubChartState,
  type MarkersHandle,
} from "./chart/chart-builders"
import { Legend, SubChartLegend, type LegendValues } from "./chart/chart-legends"
import { getSubChartDescriptors, getAllIndicatorFields, type IndicatorDescriptor } from "@/lib/indicator-registry"

const SUB_CHART_DESCRIPTORS = getSubChartDescriptors()

interface PriceChartProps {
  prices: Price[]
  indicators: Indicator[]
  annotations: Annotation[]
  showSma20?: boolean
  showSma50?: boolean
  showBollinger?: boolean
  showRsiChart?: boolean
  showMacdChart?: boolean
  chartType?: "candle" | "line"
  mainChartHeight?: number
}

interface ChartState {
  mainChart: IChartApi
  mainSeries: ReturnType<IChartApi["addSeries"]>
  overlays: OverlayState
  subCharts: SubChartState[]
}

export function PriceChart({
  prices,
  indicators,
  annotations,
  showSma20 = true,
  showSma50 = true,
  showBollinger = true,
  showRsiChart = true,
  showMacdChart = true,
  chartType = "candle",
  mainChartHeight = 400,
}: PriceChartProps) {
  const mainRef = useRef<HTMLDivElement>(null)

  // Pre-create refs for main + all possible sub-charts (hooks must be unconditional)
  const mainChartRef = useRef<IChartApi | null>(null)
  const subChartApiRefs = useRef(
    Object.fromEntries(
      SUB_CHART_DESCRIPTORS.map((d) => [d.id, { current: null as IChartApi | null }]),
    ) as Record<string, { current: IChartApi | null }>,
  )
  const allChartRefs = useMemo(
    () => [mainChartRef, ...SUB_CHART_DESCRIPTORS.map((d) => subChartApiRefs.current[d.id])],
    [],
  )
  const subContainersRef = useRef(new Map<string, HTMLDivElement>())
  const { startLifecycle } = useChartLifecycle(mainRef, allChartRefs)

  const { hoverValues, buildLookupMaps, syncCharts, setupSingleChartCrosshair } = useChartSync()

  const chartStateRef = useRef<ChartState | null>(null)
  const markersRef = useRef<MarkersHandle | null>(null)

  // Map individual show* props to generic sets
  const enabledOverlayIds = useMemo(() => {
    const ids = new Set<string>()
    if (showSma20) ids.add("sma_20")
    if (showSma50) ids.add("sma_50")
    if (showBollinger) ids.add("bb")
    return ids
  }, [showSma20, showSma50, showBollinger])

  const enabledSubCharts = useMemo<IndicatorDescriptor[]>(
    () => SUB_CHART_DESCRIPTORS.filter((d) => {
      if (d.id === "rsi") return showRsiChart
      if (d.id === "macd") return showMacdChart
      return false
    }),
    [showRsiChart, showMacdChart],
  )

  const hasSubCharts = enabledSubCharts.length > 0

  // Compute latest values for default legend display
  const latestValues = useMemo<LegendValues>(() => {
    if (!prices.length) return { indicators: {} }
    const lastPrice = prices[prices.length - 1]
    const lastIndicators = [...indicators].reverse()
    const findVal = (field: string): number | undefined =>
      (lastIndicators.find((i) => i.values[field] != null)?.values[field] ?? undefined) as number | undefined

    const indicatorValues: Record<string, number | undefined> = {}
    for (const field of getAllIndicatorFields()) {
      indicatorValues[field] = findVal(field)
    }

    return {
      o: lastPrice.open,
      h: lastPrice.high,
      l: lastPrice.low,
      c: lastPrice.close,
      indicators: indicatorValues,
    }
  }, [prices, indicators])

  // Effect 1: Create chart structure (runs only on structural changes)
  useEffect(() => {
    if (!mainRef.current) return
    // Ensure all enabled sub-chart containers are mounted
    for (const desc of enabledSubCharts) {
      if (!subContainersRef.current.has(desc.id)) return
    }

    const hideTimeAxis = hasSubCharts
    const { chart: mainChart, series: mainSeries } = createMainChart(
      mainRef.current, chartType, mainChartHeight, hideTimeAxis,
    )
    const overlays = createOverlays(mainChart)

    mainChartRef.current = mainChart

    const chartEntries: ChartEntry[] = [{ chart: mainChart, series: mainSeries }]
    const createdCharts: IChartApi[] = [mainChart]
    const subCharts: SubChartState[] = []

    for (const desc of enabledSubCharts) {
      const container = subContainersRef.current.get(desc.id)
      if (!container) continue

      const state = createSubChart(container, desc)
      subChartApiRefs.current[desc.id].current = state.chart

      // First series handle for crosshair snap
      const firstSeries = state.seriesMap.values().next().value
      if (firstSeries) {
        chartEntries.push({ chart: state.chart, series: firstSeries, snapField: state.snapField })
      }
      createdCharts.push(state.chart)
      subCharts.push(state)
    }

    // Sync all created charts
    if (chartEntries.length > 1) {
      syncCharts(chartEntries)
    } else {
      setupSingleChartCrosshair(mainChart, mainSeries)
    }

    chartStateRef.current = { mainChart, mainSeries, overlays, subCharts }

    const cleanupLifecycle = startLifecycle(createdCharts)
    const apiRefs = subChartApiRefs.current
    return () => {
      markersRef.current = null
      chartStateRef.current = null
      // Clear sub-chart refs
      for (const desc of SUB_CHART_DESCRIPTORS) {
        apiRefs[desc.id].current = null
      }
      cleanupLifecycle()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps -- enabledSubCharts identity changes trigger re-creation
  }, [chartType, showRsiChart, showMacdChart, mainChartHeight, syncCharts, setupSingleChartCrosshair, startLifecycle])

  // Effect 2: Update data in-place (runs on data and overlay toggle changes)
  useEffect(() => {
    const state = chartStateRef.current
    if (!state || !prices.length) return

    buildLookupMaps(prices, indicators)

    // Main series data
    setMainSeriesData(state.mainSeries, prices, chartType)

    // Overlay data (disabled overlays get empty data)
    setAllOverlayData(state.overlays, indicators, enabledOverlayIds)

    // Annotation markers — detach old, create new
    try { markersRef.current?.detach() } catch { /* chart may have been recreated */ }
    markersRef.current = addAnnotationMarkers(state.mainSeries, annotations)

    // Sub-chart data
    for (const sc of state.subCharts) {
      setSubChartData(sc, indicators)
    }

    // Fit content on all charts
    state.mainChart.timeScale().fitContent()
    for (const sc of state.subCharts) {
      sc.chart.timeScale().fitContent()
    }
  }, [prices, indicators, annotations, enabledOverlayIds, chartType, showRsiChart, showMacdChart, mainChartHeight, buildLookupMaps])

  const resetView = useCallback(() => {
    mainChartRef.current?.timeScale().fitContent()
    for (const desc of SUB_CHART_DESCRIPTORS) {
      subChartApiRefs.current[desc.id].current?.timeScale().fitContent()
    }
  }, [])

  const mainRoundClass = !hasSubCharts ? "rounded-md" : "rounded-t-md"

  return (
    <div className="mb-4">
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
      <div ref={mainRef} className={`w-full ${mainRoundClass} overflow-hidden`} />
      {enabledSubCharts.map((desc, idx) => (
        <Fragment key={desc.id}>
          <div className="px-1 py-1">
            <SubChartLegend descriptorId={desc.id} values={hoverValues} latest={latestValues} />
          </div>
          <div
            ref={(el) => {
              if (el) subContainersRef.current.set(desc.id, el)
              else subContainersRef.current.delete(desc.id)
            }}
            className={`w-full ${idx === enabledSubCharts.length - 1 ? "rounded-b-md" : ""} overflow-hidden`}
          />
        </Fragment>
      ))}
    </div>
  )
}
