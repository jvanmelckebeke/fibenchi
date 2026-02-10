import { useEffect, useRef, useCallback } from "react"
import {
  createChart,
  createSeriesMarkers,
  type IChartApi,
  ColorType,
  CandlestickSeries,
  LineSeries,
} from "lightweight-charts"
import type { Price, Indicator, Annotation } from "@/lib/api"

interface PriceChartProps {
  prices: Price[]
  indicators: Indicator[]
  annotations: Annotation[]
  onAnnotationClick?: (date: string) => void
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

  const syncCharts = useCallback(() => {
    const main = mainChartRef.current
    const rsi = rsiChartRef.current
    if (!main || !rsi) return

    main.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range) rsi.timeScale().setVisibleLogicalRange(range)
    })
    rsi.timeScale().subscribeVisibleLogicalRangeChange((range) => {
      if (range) main.timeScale().setVisibleLogicalRange(range)
    })
  }, [])

  useEffect(() => {
    if (!mainRef.current || !rsiRef.current || !prices.length) return

    const theme = getThemeColors()

    // Main chart
    const mainChart = createChart(mainRef.current, {
      width: mainRef.current.clientWidth,
      height: 400,
      layout: {
        background: { type: ColorType.Solid, color: theme.bg },
        textColor: theme.text,
      },
      grid: {
        vertLines: { color: theme.grid },
        horzLines: { color: theme.grid },
      },
      rightPriceScale: { borderColor: theme.border },
      timeScale: { borderColor: theme.border, timeVisible: false },
      crosshair: {
        mode: 0,
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

    // SMA lines
    if (indicators.length) {
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
      },
      grid: {
        vertLines: { color: theme.grid },
        horzLines: { color: theme.grid },
      },
      rightPriceScale: { borderColor: theme.border },
      timeScale: { borderColor: theme.border, visible: false },
    })

    const rsiSeries = rsiChart.addSeries(LineSeries, {
      color: "#8b5cf6",
      lineWidth: 2,
      priceLineVisible: false,
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
    })
    const oversold = rsiChart.addSeries(LineSeries, {
      color: "rgba(34, 197, 94, 0.5)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })

    const rsiDates = indicators.filter((i) => i.rsi !== null).map((i) => i.date)
    if (rsiDates.length) {
      overbought.setData(rsiDates.map((d) => ({ time: d, value: 70 })))
      oversold.setData(rsiDates.map((d) => ({ time: d, value: 30 })))
    }

    rsiChart.timeScale().fitContent()
    rsiChartRef.current = rsiChart

    syncCharts()

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

  return (
    <div className="space-y-0">
      <div ref={mainRef} className="w-full rounded-t-md overflow-hidden" />
      <div className="text-xs text-muted-foreground px-1 py-0.5 bg-muted/30">RSI (14)</div>
      <div ref={rsiRef} className="w-full rounded-b-md overflow-hidden" />
    </div>
  )
}
