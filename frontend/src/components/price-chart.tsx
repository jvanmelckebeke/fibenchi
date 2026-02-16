import { useEffect, useRef, useCallback, useMemo } from "react"
import {
  createChart,
  createSeriesMarkers,
  type IChartApi,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts"
import type { Price, Indicator, Annotation } from "@/lib/api"
import { baseChartOptions, useChartTheme, chartThemeOptions } from "@/lib/chart-utils"
import { useChartSync, type ChartEntry } from "@/lib/use-chart-sync"
import { BandFillPrimitive } from "./chart/bollinger-band-fill"
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
  const theme = useChartTheme()

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

    const opts = baseChartOptions(mainRef.current, mainChartHeight)

    // Main chart — hide time axis only when sub-charts exist below
    const hideMainTimeAxis = showRsiChart || showMacdChart
    const mainChart = createChart(mainRef.current, {
      ...opts,
      timeScale: { ...opts.timeScale, visible: !hideMainTimeAxis },
    })

    // Main series: candle or line
    let mainSeries: ReturnType<IChartApi["addSeries"]>
    if (chartType === "line") {
      mainSeries = mainChart.addSeries(LineSeries, {
        color: "#3b82f6",
        lineWidth: 2,
        priceLineVisible: false,
      })
      mainSeries.setData(prices.map((p) => ({ time: p.date, value: p.close })))
    } else {
      mainSeries = mainChart.addSeries(CandlestickSeries, {
        upColor: "#22c55e",
        downColor: "#ef4444",
        borderUpColor: "#22c55e",
        borderDownColor: "#ef4444",
        wickUpColor: "#22c55e",
        wickDownColor: "#ef4444",
      })
      mainSeries.setData(
        prices.map((p) => ({
          time: p.date,
          open: p.open,
          high: p.high,
          low: p.low,
          close: p.close,
        }))
      )
    }

    // Overlay indicators
    if (indicators.length) {
      if (showBollinger) {
        const bbData = indicators.filter((i) => i.bb_upper !== null && i.bb_lower !== null)

        const bbUpperLine = mainChart.addSeries(LineSeries, {
          color: "rgba(96, 165, 250, 0.4)",
          lineWidth: 1,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        })
        bbUpperLine.setData(bbData.map((i) => ({ time: i.date, value: i.bb_upper! })))

        const bbLowerLine = mainChart.addSeries(LineSeries, {
          color: "rgba(96, 165, 250, 0.4)",
          lineWidth: 1,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        })
        bbLowerLine.setData(bbData.map((i) => ({ time: i.date, value: i.bb_lower! })))

        const bandFill = new BandFillPrimitive(
          bbData.map((i) => ({ time: i.date, upper: i.bb_upper!, lower: i.bb_lower! }))
        )
        // eslint-disable-next-line @typescript-eslint/no-explicit-any -- lightweight-charts plugin API type mismatch
        bbUpperLine.attachPrimitive(bandFill as any)
      }

      if (showSma20) {
        const sma20 = mainChart.addSeries(LineSeries, {
          color: "#14b8a6",
          lineWidth: 1,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        })
        sma20.setData(
          indicators.filter((i) => i.sma_20 !== null).map((i) => ({ time: i.date, value: i.sma_20! }))
        )
      }

      if (showSma50) {
        const sma50 = mainChart.addSeries(LineSeries, {
          color: "#8b5cf6",
          lineWidth: 1,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        })
        sma50.setData(
          indicators.filter((i) => i.sma_50 !== null).map((i) => ({ time: i.date, value: i.sma_50! }))
        )
      }
    }

    // Annotation markers
    if (annotations.length) {
      const markers = annotations
        .map((a) => ({
          time: a.date,
          position: "aboveBar" as const,
          color: a.color,
          shape: "circle" as const,
          text: a.title.slice(0, 2),
        }))
        .sort((a, b) => (a.time < b.time ? -1 : 1))
      createSeriesMarkers(mainSeries, markers)
    }

    mainChart.timeScale().fitContent()
    mainChartRef.current = mainChart

    const chartEntries: ChartEntry[] = [{ chart: mainChart, series: mainSeries }]
    const createdCharts: IChartApi[] = [mainChart]

    // RSI chart
    if (showRsiChart && rsiRef.current) {
      const rsiOpts = baseChartOptions(rsiRef.current, 120)
      const rsiChart = createChart(rsiRef.current, {
        ...rsiOpts,
        rightPriceScale: {
          ...rsiOpts.rightPriceScale,
          autoScale: false,
          scaleMargins: { top: 0.05, bottom: 0.05 },
        },
      })

      const rsiSeries = rsiChart.addSeries(LineSeries, {
        color: "#8b5cf6",
        lineWidth: 2,
        priceLineVisible: false,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
      })
      rsiSeries.setData(
        indicators.filter((i) => i.rsi !== null).map((i) => ({ time: i.date, value: i.rsi! }))
      )

      // RSI threshold lines
      const thresholdOpts = {
        lineWidth: 1 as const,
        lineStyle: 2 as const,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
      }
      const overbought = rsiChart.addSeries(LineSeries, { ...thresholdOpts, color: "rgba(239, 68, 68, 0.5)" })
      const oversold = rsiChart.addSeries(LineSeries, { ...thresholdOpts, color: "rgba(34, 197, 94, 0.5)" })

      const rsiDates = indicators.filter((i) => i.rsi !== null).map((i) => i.date)
      if (rsiDates.length) {
        overbought.setData(rsiDates.map((d) => ({ time: d, value: 70 })))
        oversold.setData(rsiDates.map((d) => ({ time: d, value: 30 })))
      }

      rsiChart.timeScale().fitContent()
      rsiChartRef.current = rsiChart
      chartEntries.push({ chart: rsiChart, series: rsiSeries })
      createdCharts.push(rsiChart)
    } else {
      rsiChartRef.current = null
    }

    // MACD chart
    if (showMacdChart && macdRef.current) {
      const macdOpts = baseChartOptions(macdRef.current, 120)
      const macdChart = createChart(macdRef.current, macdOpts)

      const macdData = indicators.filter((i) => i.macd !== null)

      const macdHistSeries = macdChart.addSeries(HistogramSeries, { priceLineVisible: false, base: 0 })
      macdHistSeries.setData(
        macdData.map((i) => ({
          time: i.date,
          value: i.macd_hist!,
          color: i.macd_hist! >= 0 ? "rgba(34, 197, 94, 0.6)" : "rgba(239, 68, 68, 0.6)",
        }))
      )

      const macdLineSeries = macdChart.addSeries(LineSeries, {
        color: "#38bdf8",
        lineWidth: 2,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      })
      macdLineSeries.setData(macdData.map((i) => ({ time: i.date, value: i.macd! })))

      const macdSignalSeries = macdChart.addSeries(LineSeries, {
        color: "#fb923c",
        lineWidth: 2,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      })
      macdSignalSeries.setData(
        indicators.filter((i) => i.macd_signal !== null).map((i) => ({ time: i.date, value: i.macd_signal! }))
      )

      if (macdData.length) {
        const zeroLine = macdChart.addSeries(LineSeries, {
          color: "rgba(161, 161, 170, 0.3)",
          lineWidth: 1,
          lineStyle: 2,
          priceLineVisible: false,
          crosshairMarkerVisible: false,
        })
        zeroLine.setData(macdData.map((i) => ({ time: i.date, value: 0 })))
      }

      macdChart.timeScale().fitContent()
      macdChartRef.current = macdChart
      chartEntries.push({ chart: macdChart, series: macdLineSeries })
      createdCharts.push(macdChart)
    } else {
      macdChartRef.current = null
    }

    // Sync all created charts
    if (chartEntries.length > 1) {
      syncCharts(chartEntries)
    } else {
      setupSingleChartCrosshair(mainChart)
    }

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width
        for (const chart of createdCharts) {
          chart.applyOptions({ width: w })
        }
      }
    })
    resizeObserver.observe(mainRef.current)

    return () => {
      resizeObserver.disconnect()
      for (const chart of createdCharts) {
        chart.remove()
      }
      mainChartRef.current = null
      rsiChartRef.current = null
      macdChartRef.current = null
    }
  }, [prices, indicators, annotations, buildLookupMaps, syncCharts, setupSingleChartCrosshair, showSma20, showSma50, showBollinger, showRsiChart, showMacdChart, chartType, mainChartHeight])

  // Apply theme changes without recreating charts
  useEffect(() => {
    const opts = chartThemeOptions(theme)
    mainChartRef.current?.applyOptions(opts)
    rsiChartRef.current?.applyOptions(opts)
    macdChartRef.current?.applyOptions(opts)
  }, [theme])

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
