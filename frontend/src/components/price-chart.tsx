import { useEffect, useRef, useState, useCallback } from "react"
import {
  createChart,
  createSeriesMarkers,
  type IChartApi,
  ColorType,
  CandlestickSeries,
  LineSeries,
} from "lightweight-charts"
import type { Price, Indicator, Annotation } from "@/lib/api"
import { BandFillPrimitive } from "./chart/bollinger-band-fill"
import { Legend, RsiLegend, type LegendValues } from "./chart/chart-legends"

interface PriceChartProps {
  prices: Price[]
  indicators: Indicator[]
  annotations: Annotation[]
}

function getThemeColors() {
  const dark = document.documentElement.classList.contains("dark")
  return {
    bg: dark ? "#18181b" : "#ffffff",
    text: dark ? "#a1a1aa" : "#71717a",
    grid: dark ? "#27272a" : "#f4f4f5",
    border: dark ? "#3f3f46" : "#e4e4e7",
  }
}

export function PriceChart({ prices, indicators, annotations }: PriceChartProps) {
  const mainRef = useRef<HTMLDivElement>(null)
  const rsiRef = useRef<HTMLDivElement>(null)
  const mainChartRef = useRef<IChartApi | null>(null)
  const rsiChartRef = useRef<IChartApi | null>(null)
  const [hoverValues, setHoverValues] = useState<LegendValues | null>(null)

  // Build lookup maps
  const closeByTime = useRef(new Map<string, number>())
  const ohlcByTime = useRef(new Map<string, { o: number; h: number; l: number; c: number }>())
  const sma20ByTime = useRef(new Map<string, number>())
  const sma50ByTime = useRef(new Map<string, number>())
  const bbUpperByTime = useRef(new Map<string, number>())
  const bbLowerByTime = useRef(new Map<string, number>())
  const rsiByTime = useRef(new Map<string, number>())

  // Compute latest values for default legend display
  const latestValues = useRef<LegendValues>({})

  const syncingRef = useRef(false)

  const syncCharts = useCallback((
    mainChart: IChartApi,
    rsiChart: IChartApi,
    candleSeries: ReturnType<IChartApi["addSeries"]>,
    rsiSeries: ReturnType<IChartApi["addSeries"]>,
  ) => {
    // Sync visible range by time (not logical index) to handle different data lengths
    mainChart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      if (syncingRef.current) return
      syncingRef.current = true
      const timeRange = mainChart.timeScale().getVisibleRange()
      if (timeRange) rsiChart.timeScale().setVisibleRange(timeRange)
      syncingRef.current = false
    })
    rsiChart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      if (syncingRef.current) return
      syncingRef.current = true
      const timeRange = rsiChart.timeScale().getVisibleRange()
      if (timeRange) mainChart.timeScale().setVisibleRange(timeRange)
      syncingRef.current = false
    })

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
      }
    }

    // Sync crosshair on hover + update legend
    // Both handlers snap the crosshair on BOTH charts to the actual data values
    mainChart.subscribeCrosshairMove((param) => {
      if (param.time) {
        const key = String(param.time)
        setHoverValues(getValuesForTime(key))
      } else {
        setHoverValues(null)
      }

      if (syncingRef.current) return
      syncingRef.current = true
      if (param.time) {
        const key = String(param.time)
        const closeVal = closeByTime.current.get(key)
        if (closeVal !== undefined) {
          mainChart.setCrosshairPosition(closeVal, param.time, candleSeries)
        }
        const rsiVal = rsiByTime.current.get(key)
        if (rsiVal !== undefined) {
          rsiChart.setCrosshairPosition(rsiVal, param.time, rsiSeries)
        }
      } else {
        rsiChart.clearCrosshairPosition()
      }
      syncingRef.current = false
    })

    rsiChart.subscribeCrosshairMove((param) => {
      if (param.time) {
        const key = String(param.time)
        setHoverValues(getValuesForTime(key))
      } else {
        setHoverValues(null)
      }

      if (syncingRef.current) return
      syncingRef.current = true
      if (param.time) {
        const key = String(param.time)
        const rsiVal = rsiByTime.current.get(key)
        if (rsiVal !== undefined) {
          rsiChart.setCrosshairPosition(rsiVal, param.time, rsiSeries)
        }
        const closeVal = closeByTime.current.get(key)
        if (closeVal !== undefined) {
          mainChart.setCrosshairPosition(closeVal, param.time, candleSeries)
        }
      } else {
        mainChart.clearCrosshairPosition()
      }
      syncingRef.current = false
    })
  }, [])

  useEffect(() => {
    if (!mainRef.current || !rsiRef.current || !prices.length) return

    // Build lookup maps
    closeByTime.current.clear()
    ohlcByTime.current.clear()
    sma20ByTime.current.clear()
    sma50ByTime.current.clear()
    bbUpperByTime.current.clear()
    bbLowerByTime.current.clear()
    rsiByTime.current.clear()

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
    }

    // Latest values for default legend
    const lastPrice = prices[prices.length - 1]
    const lastIndicators = [...indicators].reverse()
    latestValues.current = {
      o: lastPrice.open,
      h: lastPrice.high,
      l: lastPrice.low,
      c: lastPrice.close,
      sma20: lastIndicators.find((i) => i.sma_20 !== null)?.sma_20 ?? undefined,
      sma50: lastIndicators.find((i) => i.sma_50 !== null)?.sma_50 ?? undefined,
      bbUpper: lastIndicators.find((i) => i.bb_upper !== null)?.bb_upper ?? undefined,
      bbLower: lastIndicators.find((i) => i.bb_lower !== null)?.bb_lower ?? undefined,
      rsi: lastIndicators.find((i) => i.rsi !== null)?.rsi ?? undefined,
    }

    const theme = getThemeColors()

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

    syncCharts(mainChart, rsiChart, candleSeries, rsiSeries)

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width
        mainChart.applyOptions({ width: w })
        rsiChart.applyOptions({ width: w })
      }
    })
    resizeObserver.observe(mainRef.current)

    return () => {
      resizeObserver.disconnect()
      mainChart.remove()
      rsiChart.remove()
      mainChartRef.current = null
      rsiChartRef.current = null
    }
  }, [prices, indicators, annotations, syncCharts])

  const resetView = useCallback(() => {
    mainChartRef.current?.timeScale().fitContent()
    rsiChartRef.current?.timeScale().fitContent()
  }, [])

  return (
    <div className="mb-4">
      <div className="flex items-center justify-between px-1 py-1">
        <Legend values={hoverValues} latest={latestValues.current} />
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
        <RsiLegend values={hoverValues} latest={latestValues.current} />
      </div>
      <div ref={rsiRef} className="w-full rounded-b-md overflow-hidden" />
    </div>
  )
}
