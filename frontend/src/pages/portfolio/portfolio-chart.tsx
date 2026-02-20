import { useEffect, useRef } from "react"
import { createChart, type IChartApi, ColorType, AreaSeries } from "lightweight-charts"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"

export function PortfolioChart({ dates, values, up }: { dates: string[]; values: number[]; up: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const { theme, startLifecycle } = useChartLifecycle(containerRef, [chartRef])

  useEffect(() => {
    if (!containerRef.current || !dates.length) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 480,
      layout: {
        background: { type: ColorType.Solid, color: theme.bg },
        textColor: theme.text,
        attributionLogo: false,
      },
      grid: { vertLines: { visible: false }, horzLines: { visible: false } },
      rightPriceScale: { visible: false },
      timeScale: { visible: false },
      crosshair: {
        vertLine: { visible: false },
        horzLine: { visible: false },
      },
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

    const series = chart.addSeries(AreaSeries, {
      lineColor: up ? "#2dd4bf" : "#ef4444",
      topColor: up ? "rgba(45, 212, 191, 0.4)" : "rgba(239, 68, 68, 0.3)",
      bottomColor: up ? "rgba(45, 212, 191, 0.05)" : "rgba(239, 68, 68, 0.05)",
      lineWidth: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })

    series.setData(
      dates.map((d, i) => ({ time: d, value: values[i] }))
    )

    chart.timeScale().fitContent()
    chartRef.current = chart

    return startLifecycle([chart])
    // eslint-disable-next-line react-hooks/exhaustive-deps -- structural dependencies only
  }, [dates, values, up, startLifecycle])

  return <div ref={containerRef} className="w-full rounded-md overflow-hidden" />
}
