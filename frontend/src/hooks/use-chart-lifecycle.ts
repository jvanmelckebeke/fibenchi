import { useCallback, useRef, useEffect, type MutableRefObject, type RefObject } from "react"
import type { IChartApi } from "lightweight-charts"
import { useChartTheme, chartThemeOptions, type ChartTheme } from "@/lib/chart-utils"

/**
 * Shared lifecycle hook for lightweight-charts instances.
 * Handles ResizeObserver, theme re-application, and cleanup.
 *
 * Usage: call `startLifecycle(charts)` at the end of your chart-creation
 * useEffect and return its result as the cleanup function.
 */
export function useChartLifecycle(
  containerRef: RefObject<HTMLDivElement | null>,
  chartRefs: MutableRefObject<IChartApi | null>[],
): { theme: ChartTheme; startLifecycle: (charts: IChartApi[]) => () => void } {
  const theme = useChartTheme()

  // Keep a stable reference to the chartRefs array
  const chartRefsRef = useRef(chartRefs)
  chartRefsRef.current = chartRefs

  // Apply theme changes to all chart refs
  useEffect(() => {
    const opts = chartThemeOptions(theme)
    for (const ref of chartRefsRef.current) {
      ref.current?.applyOptions(opts)
    }
  }, [theme])

  // Returns a cleanup function for the caller's useEffect
  const startLifecycle = useCallback((charts: IChartApi[]): (() => void) => {
    const container = containerRef.current
    if (!container) return () => {}

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const w = entry.contentRect.width
        for (const chart of charts) {
          chart.applyOptions({ width: w })
        }
      }
    })
    resizeObserver.observe(container)

    return () => {
      resizeObserver.disconnect()
      for (const chart of charts) {
        chart.remove()
      }
      for (const ref of chartRefsRef.current) {
        ref.current = null
      }
    }
  }, [containerRef])

  return { theme, startLifecycle }
}
