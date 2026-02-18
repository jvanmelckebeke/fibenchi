import { useEffect, useRef, Fragment } from "react"
import type { IChartApi } from "lightweight-charts"
import { useChartLifecycle } from "@/hooks/use-chart-lifecycle"
import {
  createSubChart,
  setSubChartData,
  type SubChartState,
} from "./chart-builders"
import { SubChartLegend } from "./chart-legends"
import { useRegisterChart, useChartHoverValues, useChartData } from "./chart-sync-provider"
import { getDescriptorById } from "@/lib/indicator-registry"

interface SubChartProps {
  /** Indicator descriptor ID (e.g. "rsi", "macd"). */
  descriptorId: string
  /** Whether to show the legend above the chart. */
  showLegend?: boolean
  /** Rounded corner class for the chart container. */
  roundedClass?: string
  /** Called with the chart API after creation. */
  onChartReady?: (chart: IChartApi) => void
  /** Called when the chart is destroyed. */
  onChartDestroy?: () => void
}

export function SubChart({
  descriptorId,
  showLegend = true,
  roundedClass = "",
  onChartReady,
  onChartDestroy,
}: SubChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const stateRef = useRef<SubChartState | null>(null)

  const { startLifecycle } = useChartLifecycle(containerRef, [chartRef])
  const registerChart = useRegisterChart()
  const { hoverValues, latestValues } = useChartHoverValues()
  const { indicators } = useChartData()

  const descriptor = getDescriptorById(descriptorId)

  // Effect 1: Create chart structure
  useEffect(() => {
    if (!containerRef.current || !descriptor) return

    const state = createSubChart(containerRef.current, descriptor)
    chartRef.current = state.chart
    stateRef.current = state

    onChartReady?.(state.chart)

    // Register with sync provider — use first series for crosshair snap
    const firstSeries = state.seriesMap.values().next().value
    let unregister: (() => void) | undefined
    if (firstSeries) {
      unregister = registerChart({
        chart: state.chart,
        series: firstSeries,
        role: descriptorId,
        snapField: state.snapField,
      })
    }

    const cleanupLifecycle = startLifecycle([state.chart])

    return () => {
      stateRef.current = null
      chartRef.current = null
      onChartDestroy?.()
      unregister?.()
      cleanupLifecycle()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- structural dependencies only
  }, [descriptorId, registerChart, startLifecycle])

  // Effect 2: Update data in-place
  useEffect(() => {
    const state = stateRef.current
    if (!state || !indicators.length) return

    setSubChartData(state, indicators)
    state.chart.timeScale().fitContent()
  }, [indicators, descriptorId])

  if (!descriptor) return null

  return (
    <Fragment>
      {showLegend && (
        <div className="px-1 py-1">
          <SubChartLegend descriptorId={descriptorId} values={hoverValues} latest={latestValues} />
        </div>
      )}
      <div ref={containerRef} className={`w-full ${roundedClass} overflow-hidden`} />
    </Fragment>
  )
}
