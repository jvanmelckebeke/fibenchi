import { useEffect, useRef, memo } from "react"
import { createChart, type IChartApi, ColorType, BaselineSeries, CrosshairMode } from "lightweight-charts"
import type { IntradayPoint } from "@/lib/types"
import { useChartTheme } from "@/lib/chart-utils"

/** 6-color session × direction palette */
const SESSION_COLORS = {
  pre:     { up: "#7dd3fc", down: "#075985" },  // sky-300 / sky-800
  regular: { up: "#10b981", down: "#ef4444" },  // emerald-500 / red-500
  post:    { up: "#c4b5fd", down: "#5b21b6" },  // violet-300 / violet-800
} as const

type SessionKey = keyof typeof SESSION_COLORS

function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `rgba(${r},${g},${b},${alpha})`
}

function getSessionPalette(session: string) {
  const colors = SESSION_COLORS[session as SessionKey] ?? SESSION_COLORS.regular
  return {
    topLineColor: colors.up,
    topFillColor1: hexToRgba(colors.up, 0.20),
    topFillColor2: hexToRgba(colors.up, 0.02),
    bottomLineColor: colors.down,
    bottomFillColor1: hexToRgba(colors.down, 0.02),
    bottomFillColor2: hexToRgba(colors.down, 0.20),
  }
}

interface SessionSegment {
  session: SessionKey
  points: IntradayPoint[]
}

/** Split points into contiguous session segments with overlap at boundaries. */
function segmentBySession(points: IntradayPoint[]): SessionSegment[] {
  if (!points.length) return []

  const segments: SessionSegment[] = []
  let segPoints: IntradayPoint[] = [points[0]]
  let segSession = (points[0].session ?? "regular") as SessionKey

  for (let i = 1; i < points.length; i++) {
    const ptSession = (points[i].session ?? "regular") as SessionKey
    if (ptSession !== segSession) {
      segments.push({ session: segSession, points: segPoints })
      // Overlap: previous segment's last point bridges the visual gap
      segPoints = [points[i - 1], points[i]]
      segSession = ptSession
    } else {
      segPoints.push(points[i])
    }
  }
  segments.push({ session: segSession, points: segPoints })

  return segments
}

/** Format intraday tick marks as 12-hour time (10:00 AM, 2:00 PM, etc.) */
function formatIntradayTime(time: number): string {
  const d = new Date(time * 1000)
  const h = d.getUTCHours()
  const m = d.getUTCMinutes()
  if (m !== 0) return ""
  const hour12 = h % 12 || 12
  const ampm = h < 12 ? "AM" : "PM"
  return `${hour12} ${ampm}`
}

export interface IntradayChartProps {
  points: IntradayPoint[]
  previousClose: number | null
  interactive?: boolean  // enables zoom/scroll/crosshair (default false)
}

export const IntradayChart = memo(function IntradayChart({
  points,
  previousClose,
  interactive = false,
}: IntradayChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesListRef = useRef<ReturnType<IChartApi["addSeries"]>[]>([])
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const currentPriceLineRef = useRef<any>(null)
  const lastLenRef = useRef(0)
  const prevCloseRef = useRef<number | null>(null)
  const segmentCountRef = useRef(0)
  const firstTimeRef = useRef<number>(0)
  const theme = useChartTheme()

  // Create chart once, recreate on theme change
  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: containerRef.current.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: theme.text,
        attributionLogo: false,
        fontSize: interactive ? 11 : 10,
      },
      grid: {
        vertLines: { visible: false },
        horzLines: { color: theme.grid, style: 2 },
      },
      rightPriceScale: {
        visible: true,
        borderVisible: false,
        scaleMargins: { top: 0.1, bottom: 0.1 },
      },
      timeScale: {
        visible: true,
        borderVisible: false,
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: formatIntradayTime,
      },
      handleScale: interactive,
      handleScroll: interactive,
      crosshair: interactive
        ? { mode: CrosshairMode.Magnet }
        : { vertLine: { visible: false }, horzLine: { visible: false } },
    })

    chartRef.current = chart
    seriesListRef.current = []
    currentPriceLineRef.current = null
    lastLenRef.current = 0
    prevCloseRef.current = null
    segmentCountRef.current = 0
    firstTimeRef.current = 0

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
      seriesListRef.current = []
      currentPriceLineRef.current = null
      lastLenRef.current = 0
      prevCloseRef.current = null
      segmentCountRef.current = 0
      firstTimeRef.current = 0
    }
  }, [theme, interactive])

  // Update data when points or previousClose change
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !points.length) return

    // Use first bar price as fallback baseline if no previous close
    const baseline = previousClose ?? points[0].price
    const segments = segmentBySession(points)
    const lastPoint = points[points.length - 1]
    const currentPrice = lastPoint.price
    const lastSession = (lastPoint.session ?? "regular") as SessionKey
    const direction = currentPrice >= baseline ? "up" : "down"
    const sessionColors = SESSION_COLORS[lastSession] ?? SESSION_COLORS.regular

    // Recreate all series when segment structure, baseline, or underlying data changes.
    // After SSE reconnect the points array is fully replaced — detect via first
    // timestamp or length shrinking so we don't feed stale indices to update().
    const dataReplaced =
      points[0]?.time !== firstTimeRef.current ||
      points.length < lastLenRef.current
    const needsRecreate =
      seriesListRef.current.length === 0 ||
      prevCloseRef.current !== baseline ||
      segments.length !== segmentCountRef.current ||
      dataReplaced

    if (needsRecreate) {
      // Remove all old series
      for (const s of seriesListRef.current) {
        chart.removeSeries(s)
      }
      seriesListRef.current = []
      currentPriceLineRef.current = null

      // Create one BaselineSeries per session segment
      for (const seg of segments) {
        const palette = getSessionPalette(seg.session)
        const series = chart.addSeries(BaselineSeries, {
          baseValue: { type: "price" as const, price: baseline },
          ...palette,
          lineWidth: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: interactive,
          autoscaleInfoProvider: (original: () => { priceRange: { minValue: number; maxValue: number } | null }) => {
            const res = original()
            if (!res?.priceRange) return res
            const { minValue, maxValue } = res.priceRange
            const range = maxValue - minValue || Math.abs(baseline) * 0.01 || 1
            const padding = range * 0.15
            return {
              ...res,
              priceRange: {
                minValue: Math.min(minValue, baseline - padding),
                maxValue: Math.max(maxValue, baseline + padding),
              },
            }
          },
        })

        series.setData(
          seg.points.map((p) => ({
            time: p.time as import("lightweight-charts").UTCTimestamp,
            value: p.price,
          }))
        )
        seriesListRef.current.push(series)
      }

      // Previous close reference line (dashed, neutral) on first series
      if (seriesListRef.current.length > 0) {
        seriesListRef.current[0].createPriceLine({
          price: baseline,
          color: theme.text,
          lineWidth: 1,
          lineStyle: 2, // dashed
          axisLabelVisible: true,
          title: "",
        })
      }

      // Current price line (solid, session-colored) on last series
      const lastSeries = seriesListRef.current[seriesListRef.current.length - 1]
      if (lastSeries) {
        currentPriceLineRef.current = lastSeries.createPriceLine({
          price: currentPrice,
          color: sessionColors[direction],
          lineWidth: 1,
          lineStyle: 0, // solid
          axisLabelVisible: true,
          title: "",
        })
      }

      lastLenRef.current = points.length
      prevCloseRef.current = baseline
      segmentCountRef.current = segments.length
      firstTimeRef.current = points[0]?.time ?? 0
      chart.timeScale().fitContent()
    } else {
      // Incremental update — append new points to last series
      const lastSeries = seriesListRef.current[seriesListRef.current.length - 1]
      if (lastSeries && points.length > lastLenRef.current) {
        try {
          for (let i = lastLenRef.current; i < points.length; i++) {
            lastSeries.update({
              time: points[i].time as import("lightweight-charts").UTCTimestamp,
              value: points[i].price,
            })
          }
          lastLenRef.current = points.length
        } catch {
          // Time conflict after data replacement — force full recreate
          for (const s of seriesListRef.current) chart.removeSeries(s)
          seriesListRef.current = []
          lastLenRef.current = 0
          segmentCountRef.current = 0
          firstTimeRef.current = 0
        }
      }

      // Update current price line position + color
      if (currentPriceLineRef.current) {
        currentPriceLineRef.current.applyOptions({
          price: currentPrice,
          color: sessionColors[direction],
        })
      }
    }
  }, [points, previousClose, theme, interactive])

  return <div ref={containerRef} className="w-full h-full" />
})
