import { useEffect, useRef } from "react"
import { createChart, type IChartApi, ColorType, AreaSeries } from "lightweight-charts"
import { usePrices } from "@/lib/queries"
import { formatPrice } from "@/lib/format"

export function SparklineChart({ symbol, currency = "USD" }: { symbol: string; currency?: string }) {
  const { data: prices } = usePrices(symbol, "3mo")
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current || !prices?.length) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 60,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "transparent",
        attributionLogo: false,
      },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      handleScale: false,
      handleScroll: false,
      crosshair: {
        vertLine: { visible: false },
        horzLine: { visible: false },
      },
    })

    const last = prices[prices.length - 1]
    const first = prices[0]
    const up = last.close >= first.close

    const series = chart.addSeries(AreaSeries, {
      lineColor: up ? "#22c55e" : "#ef4444",
      topColor: up ? "rgba(34, 197, 94, 0.3)" : "rgba(239, 68, 68, 0.3)",
      bottomColor: "transparent",
      lineWidth: 1,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })

    series.setData(
      prices.map((p) => ({ time: p.date, value: p.close }))
    )

    chart.timeScale().fitContent()
    chartRef.current = chart

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width })
        chart.timeScale().fitContent()
      }
    })
    resizeObserver.observe(containerRef.current)

    return () => {
      resizeObserver.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [prices])

  if (!prices?.length) {
    return <div className="h-[60px] flex items-center justify-center text-xs text-muted-foreground">No data</div>
  }

  const last = prices[prices.length - 1]
  const first = prices[0]
  const change = ((last.close - first.close) / first.close) * 100

  return (
    <div>
      <div ref={containerRef} className="w-full" />
      <div className="flex items-center justify-between mt-1">
        <span className="text-sm font-medium">{formatPrice(last.close, currency)}</span>
        <span className={`text-xs font-medium ${change >= 0 ? "text-green-500" : "text-red-500"}`}>
          {change >= 0 ? "+" : ""}
          {change.toFixed(1)}%
        </span>
      </div>
    </div>
  )
}
