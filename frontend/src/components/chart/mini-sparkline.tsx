import { useMemo } from "react"
import type { ThesisPerformancePoint } from "@/lib/api"

/**
 * A tiny inline SVG sparkline for a performance curve (pct over time), baseline
 * anchored at 0 and coloured by the sign of the final value.
 *
 * Intentionally a hand-rolled SVG rather than the lightweight-charts-backed
 * `SparklineChart`: the all-theses leaderboard can render dozens of these at
 * once, and one chart instance per row would block the main thread (the exact
 * hazard `DeferredSparkline` works around for the card view).
 */
export function MiniSparkline({
  points,
  width = 64,
  height = 20,
  className,
}: {
  points?: ThesisPerformancePoint[]
  width?: number
  height?: number
  className?: string
}) {
  const geom = useMemo(() => {
    if (!points || points.length < 2) return null
    const vals = points.map((p) => p.pct)
    const min = Math.min(...vals, 0)
    const max = Math.max(...vals, 0)
    const span = max - min || 1
    const stepX = width / (points.length - 1)
    const y = (v: number) => height - ((v - min) / span) * height
    const d = vals
      .map((v, i) => `${i === 0 ? "M" : "L"}${(i * stepX).toFixed(2)},${y(v).toFixed(2)}`)
      .join(" ")
    return { d, baselineY: y(0), last: vals[vals.length - 1] }
  }, [points, width, height])

  if (!geom) return <div style={{ width, height }} className={className} aria-hidden />

  const color = geom.last > 0 ? "#22c55e" : geom.last < 0 ? "#ef4444" : "currentColor"

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={className} aria-hidden>
      <line x1={0} x2={width} y1={geom.baselineY} y2={geom.baselineY} stroke="currentColor" strokeOpacity={0.15} />
      <path
        d={geom.d}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  )
}
