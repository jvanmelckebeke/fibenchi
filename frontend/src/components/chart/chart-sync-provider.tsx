import {
  createContext,
  useContext,
  useRef,
  useState,
  useCallback,
  useEffect,
  useMemo,
  type ReactNode,
} from "react"
import type { IChartApi } from "lightweight-charts"
import type { Price, Indicator } from "@/lib/api"
import type { LegendValues } from "./chart-legends"
import { getAllIndicatorFields } from "@/lib/indicator-registry"
import { useCrosshairTimeSync } from "./crosshair-time-sync"

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChartRegistration {
  chart: IChartApi
  series: ReturnType<IChartApi["addSeries"]>
  /** "main" for the candlestick/line chart, or an indicator field for sub-charts. */
  role: "main" | string
  /** Field name used to snap the crosshair y-position on this chart. */
  snapField?: string
}

interface ChartSyncContextValue {
  /** Register a chart into the sync group. Returns an unregister function. */
  register: (entry: ChartRegistration) => () => void
  /** Current crosshair hover values (null when not hovering). */
  hoverValues: LegendValues | null
  /** Latest data values (last price bar + last indicator values). */
  latestValues: LegendValues
  /** Prices array from the provider. */
  prices: Price[]
  /** Indicators array from the provider. */
  indicators: Indicator[]
}

const ChartSyncContext = createContext<ChartSyncContextValue | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface ChartSyncProviderProps {
  prices: Price[]
  indicators: Indicator[]
  children: ReactNode
}

export function ChartSyncProvider({ prices, indicators, children }: ChartSyncProviderProps) {
  const [hoverValues, setHoverValues] = useState<LegendValues | null>(null)

  // Lookup maps for fast crosshair snapping
  const closeByTime = useRef(new Map<string, number>())
  const ohlcByTime = useRef(new Map<string, { o: number; h: number; l: number; c: number }>())
  const indicatorsByTime = useRef(new Map<string, Record<string, number>>())

  // Registry of charts participating in sync
  const registrations = useRef<ChartRegistration[]>([])
  const syncingRef = useRef(false)
  // Track subscription cleanup functions per chart
  const cleanupFns = useRef(new Map<IChartApi, (() => void)[]>())

  // Stable identity for cross-provider time sync
  const identityRef = useRef({})

  // Optional cross-provider time sync context
  const timeSync = useCrosshairTimeSync()

  // Build lookup maps whenever data changes
  useEffect(() => {
    closeByTime.current.clear()
    ohlcByTime.current.clear()
    indicatorsByTime.current.clear()

    for (const p of prices) {
      closeByTime.current.set(p.date, p.close)
      ohlcByTime.current.set(p.date, { o: p.open, h: p.high, l: p.low, c: p.close })
    }
    for (const i of indicators) {
      const vals: Record<string, number> = {}
      for (const [field, value] of Object.entries(i.values)) {
        if (value != null && typeof value === "number") {
          vals[field] = value
        }
      }
      indicatorsByTime.current.set(i.date, vals)
    }
  }, [prices, indicators])

  const getValuesForTime = useCallback((key: string): LegendValues => {
    const ohlc = ohlcByTime.current.get(key)
    const indVals = indicatorsByTime.current.get(key) ?? {}
    return {
      o: ohlc?.o,
      h: ohlc?.h,
      l: ohlc?.l,
      c: ohlc?.c,
      indicators: indVals,
    }
  }, [])

  /** Snap all registered charts to a given time key using local data maps. */
  const snapChartsToTime = useCallback((key: string) => {
    const entries = registrations.current
    for (const entry of entries) {
      if (entry.role === "main") {
        const closeVal = closeByTime.current.get(key)
        if (closeVal !== undefined) {
          entry.chart.setCrosshairPosition(closeVal, key, entry.series)
        }
      } else if (entry.snapField) {
        const val = indicatorsByTime.current.get(key)?.[entry.snapField]
        if (val !== undefined) {
          entry.chart.setCrosshairPosition(val, key, entry.series)
        }
      }
    }
  }, [])

  /** Clear crosshair on all registered charts. */
  const clearAllCrosshairs = useCallback(() => {
    for (const entry of registrations.current) {
      entry.chart.clearCrosshairPosition()
    }
  }, [])

  // Subscribe to cross-provider time sync
  useEffect(() => {
    if (!timeSync) return

    const unsubscribe = timeSync.subscribe((time) => {
      if (syncingRef.current) return
      syncingRef.current = true

      if (time) {
        setHoverValues(getValuesForTime(time))
        snapChartsToTime(time)
      } else {
        setHoverValues(null)
        clearAllCrosshairs()
      }

      syncingRef.current = false
    }, identityRef.current)

    return unsubscribe
  }, [timeSync, getValuesForTime, snapChartsToTime, clearAllCrosshairs])

  // Compute latest values for default legend display
  const latestValues = useMemo<LegendValues>(() => {
    if (!prices.length) return { indicators: {} }
    const lastPrice = prices[prices.length - 1]
    const reversed = [...indicators].reverse()
    const findVal = (field: string): number | undefined =>
      (reversed.find((i) => i.values[field] != null)?.values[field] ?? undefined) as
        | number
        | undefined

    const indicatorValues: Record<string, number | undefined> = {}
    for (const field of getAllIndicatorFields()) {
      indicatorValues[field] = findVal(field)
    }

    return {
      o: lastPrice.open,
      h: lastPrice.high,
      l: lastPrice.low,
      c: lastPrice.close,
      indicators: indicatorValues,
    }
  }, [prices, indicators])

  // Wire up sync subscriptions between all registered charts
  const wireSync = useCallback(() => {
    const entries = registrations.current

    // Clean up all existing subscriptions
    for (const fns of cleanupFns.current.values()) {
      for (const fn of fns) fn()
    }
    cleanupFns.current.clear()

    if (entries.length === 0) return

    const charts = entries.map((e) => e.chart)

    // For each chart, subscribe to visible range changes and crosshair moves
    for (const source of charts) {
      const fns: (() => void)[] = []

      // Sync visible time range
      const rangeHandler = () => {
        if (syncingRef.current) return
        syncingRef.current = true
        const timeRange = source.timeScale().getVisibleRange()
        if (timeRange) {
          for (const target of charts) {
            if (target !== source) {
              try {
                target.timeScale().setVisibleRange(timeRange)
              } catch {
                // Target chart may not have data yet
              }
            }
          }
        }
        syncingRef.current = false
      }
      source.timeScale().subscribeVisibleLogicalRangeChange(rangeHandler)
      fns.push(() => source.timeScale().unsubscribeVisibleLogicalRangeChange(rangeHandler))

      // Sync crosshair position
      const crosshairHandler: Parameters<IChartApi["subscribeCrosshairMove"]>[0] = (param) => {
        if (param.time) {
          setHoverValues(getValuesForTime(String(param.time)))
        } else {
          setHoverValues(null)
        }

        if (syncingRef.current) return
        syncingRef.current = true

        if (param.time) {
          const key = String(param.time)
          for (const entry of entries) {
            if (entry.role === "main") {
              const closeVal = closeByTime.current.get(key)
              if (closeVal !== undefined) {
                entry.chart.setCrosshairPosition(closeVal, param.time, entry.series)
              }
            } else if (entry.snapField) {
              const val = indicatorsByTime.current.get(key)?.[entry.snapField]
              if (val !== undefined) {
                entry.chart.setCrosshairPosition(val, param.time, entry.series)
              }
            }
          }
          // Broadcast to other ChartSyncProviders via shared time context
          timeSync?.broadcast(key, identityRef.current)
        } else {
          for (const chart of charts) {
            if (chart !== source) chart.clearCrosshairPosition()
          }
          timeSync?.broadcast(null, identityRef.current)
        }

        syncingRef.current = false
      }
      source.subscribeCrosshairMove(crosshairHandler)
      fns.push(() => source.unsubscribeCrosshairMove(crosshairHandler))

      cleanupFns.current.set(source, fns)
    }
  }, [getValuesForTime, timeSync])

  // Single-chart crosshair setup (when only one chart is registered)
  const wireSingleCrosshair = useCallback(
    (entry: ChartRegistration) => {
      const fns: (() => void)[] = []

      const handler: Parameters<IChartApi["subscribeCrosshairMove"]>[0] = (param) => {
        if (param.time) {
          const key = String(param.time)
          setHoverValues(getValuesForTime(key))
          if (!syncingRef.current) {
            syncingRef.current = true
            const closeVal = closeByTime.current.get(key)
            if (closeVal !== undefined) {
              entry.chart.setCrosshairPosition(closeVal, param.time, entry.series)
            }
            // Broadcast to other ChartSyncProviders via shared time context
            timeSync?.broadcast(key, identityRef.current)
            syncingRef.current = false
          }
        } else {
          setHoverValues(null)
          if (!syncingRef.current) {
            timeSync?.broadcast(null, identityRef.current)
          }
        }
      }
      entry.chart.subscribeCrosshairMove(handler)
      fns.push(() => entry.chart.unsubscribeCrosshairMove(handler))

      cleanupFns.current.set(entry.chart, fns)
    },
    [getValuesForTime, timeSync],
  )

  const register = useCallback(
    (entry: ChartRegistration): (() => void) => {
      registrations.current = [...registrations.current, entry]

      // Re-wire sync with the new participant
      if (registrations.current.length === 1) {
        wireSingleCrosshair(entry)
      } else {
        wireSync()
      }

      return () => {
        // Clean up this chart's subscriptions
        const fns = cleanupFns.current.get(entry.chart)
        if (fns) {
          for (const fn of fns) fn()
          cleanupFns.current.delete(entry.chart)
        }

        registrations.current = registrations.current.filter((e) => e !== entry)

        // Re-wire remaining charts
        if (registrations.current.length === 1) {
          wireSingleCrosshair(registrations.current[0])
        } else if (registrations.current.length > 1) {
          wireSync()
        }
      }
    },
    [wireSync, wireSingleCrosshair],
  )

  const value = useMemo<ChartSyncContextValue>(
    () => ({ register, hoverValues, latestValues, prices, indicators }),
    [register, hoverValues, latestValues, prices, indicators],
  )

  return <ChartSyncContext.Provider value={value}>{children}</ChartSyncContext.Provider>
}

// ---------------------------------------------------------------------------
// Consumer hooks
// ---------------------------------------------------------------------------

/** Access the full chart sync context (must be used within ChartSyncProvider). */
function useChartSyncContext(): ChartSyncContextValue {
  const ctx = useContext(ChartSyncContext)
  if (!ctx) throw new Error("useChartSyncContext must be used within a ChartSyncProvider")
  return ctx
}

/** Register a chart into the sync group. Call inside a chart component's mount effect. */
// eslint-disable-next-line react-refresh/only-export-components
export function useRegisterChart() {
  const { register } = useChartSyncContext()
  return register
}

/** Read crosshair-position hover values. Works from any component inside ChartSyncProvider. */
// eslint-disable-next-line react-refresh/only-export-components
export function useChartHoverValues(): { hoverValues: LegendValues | null; latestValues: LegendValues } {
  const { hoverValues, latestValues } = useChartSyncContext()
  return { hoverValues, latestValues }
}

/** Access the prices and indicators data from the provider. */
// eslint-disable-next-line react-refresh/only-export-components
export function useChartData(): { prices: Price[]; indicators: Indicator[] } {
  const { prices, indicators } = useChartSyncContext()
  return { prices, indicators }
}
