import { useEffect, useRef, useCallback, useMemo } from "react"
import type { IChartApi } from "lightweight-charts"
import type { Price, Indicator, Annotation } from "@/lib/api"
import { useChartSync, type ChartEntry } from "@/lib/use-chart-sync"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"
import {
  createMainChart,
  createOverlaySeries,
  createRsiSubChart,
  createMacdSubChart,
  setMainSeriesData,
  setOverlayData,
  setRsiData,
  setMacdData,
  addAnnotationMarkers,
  type OverlaySeries,
  type RsiChartState,
  type MacdChartState,
  type MarkersHandle,
} from "./chart/chart-builders"
import { Legend, RsiLegend, MacdLegend, type LegendValues } from "./chart/chart-legends"

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
  overlays: OverlaySeries
  rsi: RsiChartState | null
  macd: MacdChartState | null
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
  const rsiRef = useRef<HTMLDivElement>(null)
  const macdRef = useRef<HTMLDivElement>(null)
  const mainChartRef = useRef<IChartApi | null>(null)
  const rsiChartRef = useRef<IChartApi | null>(null)
  const macdChartRef = useRef<IChartApi | null>(null)
  const { startLifecycle } = useChartLifecycle(mainRef, [mainChartRef, rsiChartRef, macdChartRef])

  const { hoverValues, buildLookupMaps, syncCharts, setupSingleChartCrosshair } = useChartSync()

  const chartStateRef = useRef<ChartState | null>(null)
  const markersRef = useRef<MarkersHandle | null>(null)

  // Compute latest values for default legend display
  const latestValues = useMemo<LegendValues>(() => {
    if (!prices.length) return {}
    const lastPrice = prices[prices.length - 1]
    const lastIndicators = [...indicators].reverse()
    return {
      o: lastPrice.open,
      h: lastPrice.high,
      l: lastPrice.low,
      c: lastPrice.close,
      sma20: showSma20 ? (lastIndicators.find((i) => i.sma_20 !== null)?.sma_20 ?? undefined) : undefined,
      sma50: showSma50 ? (lastIndicators.find((i) => i.sma_50 !== null)?.sma_50 ?? undefined) : undefined,
      bbUpper: showBollinger ? (lastIndicators.find((i) => i.bb_upper !== null)?.bb_upper ?? undefined) : undefined,
      bbLower: showBollinger ? (lastIndicators.find((i) => i.bb_lower !== null)?.bb_lower ?? undefined) : undefined,
      rsi: showRsiChart ? (lastIndicators.find((i) => i.rsi !== null)?.rsi ?? undefined) : undefined,
      macd: showMacdChart ? (lastIndicators.find((i) => i.macd !== null)?.macd ?? undefined) : undefined,
      macdSignal: showMacdChart ? (lastIndicators.find((i) => i.macd_signal !== null)?.macd_signal ?? undefined) : undefined,
      macdHist: showMacdChart ? (lastIndicators.find((i) => i.macd_hist !== null)?.macd_hist ?? undefined) : undefined,
    }
  }, [prices, indicators, showSma20, showSma50, showBollinger, showRsiChart, showMacdChart])

  // Effect 1: Create chart structure (runs only on structural changes)
  useEffect(() => {
    if (!mainRef.current) return
    if (showRsiChart && !rsiRef.current) return
    if (showMacdChart && !macdRef.current) return

    const hideTimeAxis = showRsiChart || showMacdChart
    const { chart: mainChart, series: mainSeries } = createMainChart(
      mainRef.current, chartType, mainChartHeight, hideTimeAxis,
    )
    const overlays = createOverlaySeries(mainChart)

    mainChartRef.current = mainChart

    const chartEntries: ChartEntry[] = [{ chart: mainChart, series: mainSeries }]
    const createdCharts: IChartApi[] = [mainChart]

    let rsi: RsiChartState | null = null
    if (showRsiChart && rsiRef.current) {
      rsi = createRsiSubChart(rsiRef.current)
      rsiChartRef.current = rsi.chart
      chartEntries.push({ chart: rsi.chart, series: rsi.series })
      createdCharts.push(rsi.chart)
    } else {
      rsiChartRef.current = null
    }

    let macd: MacdChartState | null = null
    if (showMacdChart && macdRef.current) {
      macd = createMacdSubChart(macdRef.current)
      macdChartRef.current = macd.chart
      chartEntries.push({ chart: macd.chart, series: macd.line })
      createdCharts.push(macd.chart)
    } else {
      macdChartRef.current = null
    }

    // Sync all created charts
    if (chartEntries.length > 1) {
      syncCharts(chartEntries)
    } else {
      setupSingleChartCrosshair(mainChart, mainSeries)
    }

    chartStateRef.current = { mainChart, mainSeries, overlays, rsi, macd }

    const cleanupLifecycle = startLifecycle(createdCharts)
    return () => {
      markersRef.current = null
      chartStateRef.current = null
      cleanupLifecycle()
    }
  }, [chartType, showRsiChart, showMacdChart, mainChartHeight, syncCharts, setupSingleChartCrosshair, startLifecycle])

  // Effect 2: Update data in-place (runs on data and overlay toggle changes)
  useEffect(() => {
    const state = chartStateRef.current
    if (!state || !prices.length) return

    buildLookupMaps(prices, indicators)

    // Main series data
    setMainSeriesData(state.mainSeries, prices, chartType)

    // Overlay data (hidden overlays get empty data)
    setOverlayData(state.overlays, indicators, {
      sma20: showSma20,
      sma50: showSma50,
      bollinger: showBollinger,
    })

    // Annotation markers — detach old, create new
    try { markersRef.current?.detach() } catch { /* chart may have been recreated */ }
    markersRef.current = addAnnotationMarkers(state.mainSeries, annotations)

    // RSI data
    if (state.rsi) setRsiData(state.rsi, indicators)

    // MACD data
    if (state.macd) setMacdData(state.macd, indicators)

    // Fit content on all charts
    state.mainChart.timeScale().fitContent()
    state.rsi?.chart.timeScale().fitContent()
    state.macd?.chart.timeScale().fitContent()
  }, [prices, indicators, annotations, showSma20, showSma50, showBollinger, chartType, showRsiChart, showMacdChart, mainChartHeight, buildLookupMaps])

  const resetView = useCallback(() => {
    mainChartRef.current?.timeScale().fitContent()
    rsiChartRef.current?.timeScale().fitContent()
    macdChartRef.current?.timeScale().fitContent()
  }, [])

  const mainRoundClass = !showRsiChart && !showMacdChart ? "rounded-md" : "rounded-t-md"

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
      {showRsiChart && (
        <>
          <div className="px-1 py-1">
            <RsiLegend values={hoverValues} latest={latestValues} />
          </div>
          <div ref={rsiRef} className="w-full overflow-hidden" />
        </>
      )}
      {showMacdChart && (
        <>
          <div className="px-1 py-1">
            <MacdLegend values={hoverValues} latest={latestValues} />
          </div>
          <div ref={macdRef} className={`w-full ${!showRsiChart && !showMacdChart ? "" : "rounded-b-md"} overflow-hidden`} />
        </>
      )}
    </div>
  )
}
