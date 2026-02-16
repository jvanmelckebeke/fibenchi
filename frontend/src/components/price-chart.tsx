import { useEffect, useRef, useCallback, useMemo } from "react"
import type { IChartApi } from "lightweight-charts"
import type { Price, Indicator, Annotation } from "@/lib/api"
import { useChartSync, type ChartEntry } from "@/lib/use-chart-sync"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"
import {
  createMainChart,
  addBollingerBands,
  addSmaOverlays,
  addAnnotationMarkers,
  createRsiSubChart,
  createMacdSubChart,
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

  useEffect(() => {
    if (!mainRef.current || !prices.length) return
    if (showRsiChart && !rsiRef.current) return
    if (showMacdChart && !macdRef.current) return

    buildLookupMaps(prices, indicators)

    // Main chart
    const hideTimeAxis = showRsiChart || showMacdChart
    const { chart: mainChart, series: mainSeries } = createMainChart(
      mainRef.current, prices, chartType, mainChartHeight, hideTimeAxis,
    )

    // Overlays
    if (indicators.length) {
      if (showBollinger) addBollingerBands(mainChart, indicators)
      addSmaOverlays(mainChart, indicators, { sma20: showSma20, sma50: showSma50 })
    }
    addAnnotationMarkers(mainSeries, annotations)

    mainChart.timeScale().fitContent()
    mainChartRef.current = mainChart

    const chartEntries: ChartEntry[] = [{ chart: mainChart, series: mainSeries }]
    const createdCharts: IChartApi[] = [mainChart]

    // RSI sub-chart
    if (showRsiChart && rsiRef.current) {
      const rsi = createRsiSubChart(rsiRef.current, indicators)
      rsiChartRef.current = rsi.chart
      chartEntries.push({ chart: rsi.chart, series: rsi.series })
      createdCharts.push(rsi.chart)
    } else {
      rsiChartRef.current = null
    }

    // MACD sub-chart
    if (showMacdChart && macdRef.current) {
      const macd = createMacdSubChart(macdRef.current, indicators)
      macdChartRef.current = macd.chart
      chartEntries.push({ chart: macd.chart, series: macd.series })
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

    return startLifecycle(createdCharts)
  }, [prices, indicators, annotations, buildLookupMaps, syncCharts, setupSingleChartCrosshair, showSma20, showSma50, showBollinger, showRsiChart, showMacdChart, chartType, mainChartHeight, startLifecycle])

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
