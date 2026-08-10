import { useCallback, useRef, useEffect, type MutableRefObject, type RefObject } from "react"
import type { IChartApi } from "lightweight-charts"
import { useChartTheme, chartThemeOptions, type ChartTheme } from "@/lib/chart-utils"

/**
 * Observe `container` and push its width to every chart on resize (refitting
 * the time scale unless `refit: false`); returns a cleanup that disconnects
 * the observer and removes the charts. The option-agnostic primitive used by
 * the bespoke sparkline / intraday charts, which opt out of the full themed
 * lifecycle below, and by `startLifecycle` itself — the single ResizeObserver
 * implementation both lifecycles share.
 */
export function attachResizeAndCleanup(
  container: HTMLElement,
  charts: IChartApi[],
  { refit = true }: { refit?: boolean } = {},
): () => void {
  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      for (const chart of charts) {
        chart.applyOptions({ width: entry.contentRect.width })
        if (refit) chart.timeScale().fitContent()
      }
    }
  })
  resizeObserver.observe(container)
  return () => {
    resizeObserver.disconnect()
    for (const chart of charts) {
      chart.remove()
    }
  }
}

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
  useEffect(() => {
    chartRefsRef.current = chartRefs
  })

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

    const detach = attachResizeAndCleanup(container, charts, { refit: false })

    return () => {
      detach()
      for (const ref of chartRefsRef.current) {
        ref.current = null
      }
    }
  }, [containerRef])

  return { theme, startLifecycle }
}
