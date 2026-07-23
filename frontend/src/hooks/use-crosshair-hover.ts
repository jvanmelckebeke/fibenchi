import { useState, useRef, useCallback, type MutableRefObject } from "react"
import type { IChartApi } from "lightweight-charts"

/**
 * Crosshair-driven legend state for the pseudo-ETF breakdown charts. The chart
 * populates `hoverRef` (keyed by `String(time)`) inside its create-effect; on
 * crosshair move the matching entry becomes the live hover value, falling back
 * to `latest` (the most recent point) when the cursor leaves the chart.
 *
 * Simple charts call `subscribe(chart)`; charts that also need to snap the
 * crosshair use `setHover` + `hoverRef` from their own handler instead.
 */
export function useCrosshairHover<H>(latest: H | null): {
  hoverRef: MutableRefObject<Map<string, H>>
  setHover: (h: H | null) => void
  subscribe: (chart: IChartApi) => void
  displayData: H | null
} {
  const [hover, setHover] = useState<H | null>(null)
  const hoverRef = useRef(new Map<string, H>())

  const subscribe = useCallback((chart: IChartApi) => {
    chart.subscribeCrosshairMove((param) => {
      if (param.time) {
        const h = hoverRef.current.get(String(param.time))
        if (h !== undefined) setHover(h)
      } else {
        setHover(null)
      }
    })
  }, [])

  return { hoverRef, setHover, subscribe, displayData: hover ?? latest }
}
