import { useEffect, useRef, useState, useCallback, useMemo } from "react"
import {
  createChart,
  createSeriesMarkers,
  type IChartApi,
  ColorType,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts"
import type { Price, Indicator, Annotation } from "@/lib/api"
import { getChartTheme, useChartTheme, chartThemeOptions } from "@/lib/chart-utils"
import { BandFillPrimitive } from "./chart/bollinger-band-fill"
import { Legend, RsiLegend, MacdLegend, type LegendValues } from "./chart/chart-legends"

interface PriceChartProps {
  prices: Price[]
  indicators: Indicator[]
  annotations: Annotation[]
}

export function PriceChart({ prices, indicators, annotations }: PriceChartProps) {
  const mainRef = useRef<HTMLDivElement>(null)
  const rsiRef = useRef<HTMLDivElement>(null)
  const macdRef = useRef<HTMLDivElement>(null)
  const mainChartRef = useRef<IChartApi | null>(null)
  const rsiChartRef = useRef<IChartApi | null>(null)
  const macdChartRef = useRef<IChartApi | null>(null)
  const [hoverValues, setHoverValues] = useState<LegendValues | null>(null)
  const theme = useChartTheme()

  // Build lookup maps
  const closeByTime = useRef(new Map<string, number>())
  const ohlcByTime = useRef(new Map<string, { o: number; h: number; l: number; c: number }>())
  const sma20ByTime = useRef(new Map<string, number>())
  const sma50ByTime = useRef(new Map<string, number>())
  const bbUpperByTime = useRef(new Map<string, number>())
  const bbLowerByTime = useRef(new Map<string, number>())
  const rsiByTime = useRef(new Map<string, number>())
  const macdByTime = useRef(new Map<string, number>())
  const macdSignalByTime = useRef(new Map<string, number>())
  const macdHistByTime = useRef(new Map<string, number>())

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
      sma20: lastIndicators.find((i) => i.sma_20 !== null)?.sma_20 ?? undefined,
      sma50: lastIndicators.find((i) => i.sma_50 !== null)?.sma_50 ?? undefined,
      bbUpper: lastIndicators.find((i) => i.bb_upper !== null)?.bb_upper ?? undefined,
      bbLower: lastIndicators.find((i) => i.bb_lower !== null)?.bb_lower ?? undefined,
      rsi: lastIndicators.find((i) => i.rsi !== null)?.rsi ?? undefined,
      macd: lastIndicators.find((i) => i.macd !== null)?.macd ?? undefined,
      macdSignal: lastIndicators.find((i) => i.macd_signal !== null)?.macd_signal ?? undefined,
      macdHist: lastIndicators.find((i) => i.macd_hist !== null)?.macd_hist ?? undefined,
    }
  }, [prices, indicators])

  const syncingRef = useRef(false)

  const syncCharts = useCallback((
    mainChart: IChartApi,
    rsiChart: IChartApi,
    macdChart: IChartApi,
    candleSeries: ReturnType<IChartApi["addSeries"]>,
    rsiSeries: ReturnType<IChartApi["addSeries"]>,
    macdLineSeries: ReturnType<IChartApi["addSeries"]>,
  ) => {
    const charts = [mainChart, rsiChart, macdChart]

    // Sync visible range across all 3 charts
    for (const source of charts) {
      source.timeScale().subscribeVisibleLogicalRangeChange(() => {
        if (syncingRef.current) return
        syncingRef.current = true
        const timeRange = source.timeScale().getVisibleRange()
        if (timeRange) {
          for (const target of charts) {
            if (target !== source) target.timeScale().setVisibleRange(timeRange)
          }
        }
        syncingRef.current = false
      })
    }

    const getValuesForTime = (key: string): LegendValues => {
      const ohlc = ohlcByTime.current.get(key)
      return {
        o: ohlc?.o,
        h: ohlc?.h,
        l: ohlc?.l,
        c: ohlc?.c,
        sma20: sma20ByTime.current.get(key),
        sma50: sma50ByTime.current.get(key),
        bbUpper: bbUpperByTime.current.get(key),
        bbLower: bbLowerByTime.current.get(key),
        rsi: rsiByTime.current.get(key),
        macd: macdByTime.current.get(key),
        macdSignal: macdSignalByTime.current.get(key),
        macdHist: macdHistByTime.current.get(key),
      }
    }

    // Snap crosshair on all charts to actual data values
    const snapCrosshair = (key: string, time: Parameters<IChartApi["setCrosshairPosition"]>[1]) => {
      const closeVal = closeByTime.current.get(key)
      if (closeVal !== undefined) mainChart.setCrosshairPosition(closeVal, time, candleSeries)
      const rsiVal = rsiByTime.current.get(key)
      if (rsiVal !== undefined) rsiChart.setCrosshairPosition(rsiVal, time, rsiSeries)
      const macdVal = macdByTime.current.get(key)
      if (macdVal !== undefined) macdChart.setCrosshairPosition(macdVal, time, macdLineSeries)
    }

    const clearOtherCrosshairs = (source: IChartApi) => {
      for (const chart of charts) {
        if (chart !== source) chart.clearCrosshairPosition()
      }
    }

    // Sync crosshair on hover + update legend for all charts
    for (const source of charts) {
      source.subscribeCrosshairMove((param) => {
        if (param.time) {
          const key = String(param.time)
          setHoverValues(getValuesForTime(key))
        } else {
          setHoverValues(null)
        }

        if (syncingRef.current) return
        syncingRef.current = true
        if (param.time) {
          snapCrosshair(String(param.time), param.time)
        } else {
          clearOtherCrosshairs(source)
        }
        syncingRef.current = false
      })
    }
  }, [])

  useEffect(() => {
    if (!mainRef.current || !rsiRef.current || !macdRef.current || !prices.length) return

    // Build lookup maps
    closeByTime.current.clear()
    ohlcByTime.current.clear()
    sma20ByTime.current.clear()
    sma50ByTime.current.clear()
    bbUpperByTime.current.clear()
    bbLowerByTime.current.clear()
    rsiByTime.current.clear()
    macdByTime.current.clear()
    macdSignalByTime.current.clear()
    macdHistByTime.current.clear()

    for (const p of prices) {
      closeByTime.current.set(p.date, p.close)
      ohlcByTime.current.set(p.date, { o: p.open, h: p.high, l: p.low, c: p.close })
    }
    for (const i of indicators) {
      if (i.sma_20 !== null) sma20ByTime.current.set(i.date, i.sma_20)
      if (i.sma_50 !== null) sma50ByTime.current.set(i.date, i.sma_50)
      if (i.bb_upper !== null) bbUpperByTime.current.set(i.date, i.bb_upper)
      if (i.bb_lower !== null) bbLowerByTime.current.set(i.date, i.bb_lower)
      if (i.rsi !== null) rsiByTime.current.set(i.date, i.rsi)
      if (i.macd !== null) macdByTime.current.set(i.date, i.macd)
      if (i.macd_signal !== null) macdSignalByTime.current.set(i.date, i.macd_signal)
      if (i.macd_hist !== null) macdHistByTime.current.set(i.date, i.macd_hist)
    }

    const theme = getChartTheme()

    // Main chart
    const mainChart = createChart(mainRef.current, {
      width: mainRef.current.clientWidth,
      height: 400,
      layout: {
        background: { type: ColorType.Solid, color: theme.bg },
        textColor: theme.text,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: theme.grid },
        horzLines: { color: theme.grid },
      },
      rightPriceScale: { borderColor: theme.border },
      timeScale: { borderColor: theme.border, visible: false },
      crosshair: { mode: 0 },
      handleScroll: {
        horzTouchDrag: true,
        vertTouchDrag: false,
        mouseWheel: false,
        pressedMouseMove: true,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: false,
        axisDoubleClickReset: { time: true, price: false },
      },
    })

    const candleSeries = mainChart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    })

    candleSeries.setData(
      prices.map((p) => ({
        time: p.date,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      }))
    )

    // Overlay indicators
    if (indicators.length) {
      // Bollinger Bands — line series for borders + custom primitive for band fill
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

      // Attach band fill primitive to the upper BB line series
      const bandFill = new BandFillPrimitive(
        bbData.map((i) => ({ time: i.date, upper: i.bb_upper!, lower: i.bb_lower! }))
      )
      // eslint-disable-next-line @typescript-eslint/no-explicit-any -- lightweight-charts plugin API type mismatch
      bbUpperLine.attachPrimitive(bandFill as any)

      // SMA lines
      const sma20 = mainChart.addSeries(LineSeries, {
        color: "#14b8a6",
        lineWidth: 1,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      })
      sma20.setData(
        indicators
          .filter((i) => i.sma_20 !== null)
          .map((i) => ({ time: i.date, value: i.sma_20! }))
      )

      const sma50 = mainChart.addSeries(LineSeries, {
        color: "#8b5cf6",
        lineWidth: 1,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      })
      sma50.setData(
        indicators
          .filter((i) => i.sma_50 !== null)
          .map((i) => ({ time: i.date, value: i.sma_50! }))
      )
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

      createSeriesMarkers(candleSeries, markers)
    }

    mainChart.timeScale().fitContent()
    mainChartRef.current = mainChart

    // RSI chart
    const rsiChart = createChart(rsiRef.current, {
      width: rsiRef.current.clientWidth,
      height: 120,
      layout: {
        background: { type: ColorType.Solid, color: theme.bg },
        textColor: theme.text,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: theme.grid },
        horzLines: { color: theme.grid },
      },
      rightPriceScale: {
        borderColor: theme.border,
        autoScale: false,
        scaleMargins: { top: 0.05, bottom: 0.05 },
      },
      timeScale: { borderColor: theme.border, timeVisible: false },
      crosshair: { mode: 0 },
      handleScroll: {
        horzTouchDrag: true,
        vertTouchDrag: false,
        mouseWheel: false,
        pressedMouseMove: true,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: false,
        axisDoubleClickReset: { time: true, price: false },
      },
    })

    const rsiSeries = rsiChart.addSeries(LineSeries, {
      color: "#8b5cf6",
      lineWidth: 2,
      priceLineVisible: false,
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: 0, maxValue: 100 },
      }),
    })

    rsiSeries.setData(
      indicators
        .filter((i) => i.rsi !== null)
        .map((i) => ({ time: i.date, value: i.rsi! }))
    )

    // RSI threshold lines
    const overbought = rsiChart.addSeries(LineSeries, {
      color: "rgba(239, 68, 68, 0.5)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: 0, maxValue: 100 },
      }),
    })
    const oversold = rsiChart.addSeries(LineSeries, {
      color: "rgba(34, 197, 94, 0.5)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
      autoscaleInfoProvider: () => ({
        priceRange: { minValue: 0, maxValue: 100 },
      }),
    })

    const rsiDates = indicators.filter((i) => i.rsi !== null).map((i) => i.date)
    if (rsiDates.length) {
      overbought.setData(rsiDates.map((d) => ({ time: d, value: 70 })))
      oversold.setData(rsiDates.map((d) => ({ time: d, value: 30 })))
    }

    rsiChart.timeScale().fitContent()
    rsiChartRef.current = rsiChart

    // MACD chart
    const macdChart = createChart(macdRef.current, {
      width: macdRef.current.clientWidth,
      height: 120,
      layout: {
        background: { type: ColorType.Solid, color: theme.bg },
        textColor: theme.text,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: theme.grid },
        horzLines: { color: theme.grid },
      },
      rightPriceScale: { borderColor: theme.border },
      timeScale: { borderColor: theme.border, timeVisible: false },
      crosshair: { mode: 0 },
      handleScroll: {
        horzTouchDrag: true,
        vertTouchDrag: false,
        mouseWheel: false,
        pressedMouseMove: true,
      },
      handleScale: {
        mouseWheel: true,
        pinch: true,
        axisPressedMouseMove: false,
        axisDoubleClickReset: { time: true, price: false },
      },
    })

    const macdData = indicators.filter((i) => i.macd !== null)

    // MACD histogram (rendered first so lines draw on top)
    const macdHistSeries = macdChart.addSeries(HistogramSeries, {
      priceLineVisible: false,
      base: 0,
    })
    macdHistSeries.setData(
      macdData.map((i) => ({
        time: i.date,
        value: i.macd_hist!,
        color: i.macd_hist! >= 0 ? "rgba(34, 197, 94, 0.6)" : "rgba(239, 68, 68, 0.6)",
      }))
    )

    // MACD line
    const macdLineSeries = macdChart.addSeries(LineSeries, {
      color: "#38bdf8",
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })
    macdLineSeries.setData(
      macdData.map((i) => ({ time: i.date, value: i.macd! }))
    )

    // Signal line
    const macdSignalSeries = macdChart.addSeries(LineSeries, {
      color: "#fb923c",
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })
    macdSignalSeries.setData(
      indicators
        .filter((i) => i.macd_signal !== null)
        .map((i) => ({ time: i.date, value: i.macd_signal! }))
    )

    // Zero line
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

    syncCharts(mainChart, rsiChart, macdChart, candleSeries, rsiSeries, macdLineSeries)

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width
        mainChart.applyOptions({ width: w })
        rsiChart.applyOptions({ width: w })
        macdChart.applyOptions({ width: w })
      }
    })
    resizeObserver.observe(mainRef.current)

    return () => {
      resizeObserver.disconnect()
      mainChart.remove()
      rsiChart.remove()
      macdChart.remove()
      mainChartRef.current = null
      rsiChartRef.current = null
      macdChartRef.current = null
    }
  }, [prices, indicators, annotations, syncCharts])

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
      <div ref={mainRef} className="w-full rounded-t-md overflow-hidden" />
      <div className="px-1 py-1">
        <RsiLegend values={hoverValues} latest={latestValues} />
      </div>
      <div ref={rsiRef} className="w-full overflow-hidden" />
      <div className="px-1 py-1">
        <MacdLegend values={hoverValues} latest={latestValues} />
      </div>
      <div ref={macdRef} className="w-full rounded-b-md overflow-hidden" />
    </div>
  )
}
