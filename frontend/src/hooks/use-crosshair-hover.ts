import { useState, useRef, useCallback, type MutableRefObject } from "react"
import type { IChartApi, Time } from "lightweight-charts"

/**
 * Crosshair-driven legend state for the pseudo-ETF breakdown charts. The chart
 * populates `hoverRef` (keyed by `String(time)`) inside its create-effect; on
 * crosshair move the matching entry becomes the live hover value, falling back
 * to `latest` (the most recent point) when the cursor leaves the chart.
 *
 * `subscribe(chart)` owns the whole crosshair subscription. Charts that also
 * react to the resolved hover (e.g. snapping the crosshair onto a series) pass
 * `onHover`; it runs inside the handler behind a re-entrancy guard, so a
 * snap-triggered crosshair event can't recurse.
 */
export function useCrosshairHover<H>(latest: H | null): {
  hoverRef: MutableRefObject<Map<string, H>>
  subscribe: (chart: IChartApi, onHover?: (h: H, time: Time) => void) => void
  displayData: H | null
} {
  const [hover, setHover] = useState<H | null>(null)
  const hoverRef = useRef(new Map<string, H>())

  const subscribe = useCallback(
    (chart: IChartApi, onHover?: (h: H, time: Time) => void) => {
      let reentrant = false
      chart.subscribeCrosshairMove((param) => {
        if (param.time) {
          const h = hoverRef.current.get(String(param.time))
          if (h !== undefined) {
            setHover(h)
            if (onHover && !reentrant) {
              reentrant = true
              onHover(h, param.time)
              reentrant = false
            }
          }
        } else {
          setHover(null)
        }
      })
    },
    [],
  )

  return { hoverRef, subscribe, displayData: hover ?? latest }
}
