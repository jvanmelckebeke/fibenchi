import { useEffect, useRef, useState, useCallback } from "react"
import { createChart, type IChartApi, ColorType, AreaSeries } from "lightweight-charts"
import { Skeleton } from "@/components/ui/skeleton"
import type { SparklinePoint } from "@/lib/api"

export function SparklineChart({
  batchData,
}: {
  batchData?: SparklinePoint[]
}) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current || !batchData?.length) return

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

    const last = batchData[batchData.length - 1]
    const first = batchData[0]
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
      batchData.map((p) => ({ time: p.date, value: p.close }))
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
  }, [batchData])

  if (!batchData) {
    return <Skeleton className="h-[60px] w-full rounded" />
  }

  if (!batchData.length) {
    return <div className="h-[60px] flex items-center justify-center text-xs text-muted-foreground">No data</div>
  }

  return <div ref={containerRef} className="w-full" />
}

/**
 * Wrapper that defers sparkline chart creation until the element is visible
 * in the viewport. This prevents 20+ chart instances from being created
 * simultaneously when switching from table to card view, which would block
 * the main thread and cause a visible freeze.
 */
export function DeferredSparkline(props: {
  batchData?: SparklinePoint[]
}) {
  const [isVisible, setIsVisible] = useState(false)
  const sentinelRef = useRef<HTMLDivElement>(null)

  const observerCallback = useCallback((entries: IntersectionObserverEntry[]) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        setIsVisible(true)
      }
    }
  }, [])

  const hasData = !!props.batchData

  useEffect(() => {
    const el = sentinelRef.current
    if (!el || isVisible) return

    const observer = new IntersectionObserver(observerCallback, {
      rootMargin: "100px",
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [isVisible, observerCallback, hasData])

  if (isVisible) {
    return <SparklineChart {...props} />
  }

  // Sentinel div: same height as chart, observed for intersection
  if (!props.batchData) {
    return <Skeleton className="h-[60px] w-full rounded" />
  }

  return <div ref={sentinelRef} className="h-[60px] w-full" />
}
