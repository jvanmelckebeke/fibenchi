import { useRef, useState, useCallback } from "react"
import type { IChartApi } from "lightweight-charts"
import type { Price, Indicator } from "@/lib/api"
import type { LegendValues } from "@/components/chart/chart-legends"

export interface ChartEntry {
  chart: IChartApi
  series: ReturnType<IChartApi["addSeries"]>
  /** Field name used to snap the crosshair y-position on this chart. */
  snapField?: string
}

export function useChartSync() {
  const [hoverValues, setHoverValues] = useState<LegendValues | null>(null)

  const closeByTime = useRef(new Map<string, number>())
  const ohlcByTime = useRef(new Map<string, { o: number; h: number; l: number; c: number }>())
  const indicatorsByTime = useRef(new Map<string, Record<string, number>>())

  const syncingRef = useRef(false)

  const buildLookupMaps = useCallback((prices: Price[], indicators: Indicator[]) => {
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
  }, [])

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

  const syncCharts = useCallback((chartEntries: ChartEntry[]) => {
    const charts = chartEntries.map((e) => e.chart)

    // Sync visible range across all charts
    for (const source of charts) {
      source.timeScale().subscribeVisibleLogicalRangeChange(() => {
        if (syncingRef.current) return
        syncingRef.current = true
        const timeRange = source.timeScale().getVisibleRange()
        if (timeRange) {
          for (const target of charts) {
            if (target !== source) {
              try {
                target.timeScale().setVisibleRange(timeRange)
              } catch {
                // Target chart may not have data yet — skip until next sync
              }
            }
          }
        }
        syncingRef.current = false
      })
    }

    const snapCrosshair = (key: string, time: Parameters<IChartApi["setCrosshairPosition"]>[1]) => {
      for (const entry of chartEntries) {
        if (entry === chartEntries[0]) {
          // Main chart — snap to close price
          const closeVal = closeByTime.current.get(key)
          if (closeVal !== undefined) {
            entry.chart.setCrosshairPosition(closeVal, time, entry.series)
          }
        } else if (entry.snapField) {
          // Sub-chart — snap to its designated field
          const val = indicatorsByTime.current.get(key)?.[entry.snapField]
          if (val !== undefined) {
            entry.chart.setCrosshairPosition(val, time, entry.series)
          }
        }
      }
    }

    const clearOtherCrosshairs = (source: IChartApi) => {
      for (const chart of charts) {
        if (chart !== source) chart.clearCrosshairPosition()
      }
    }

    for (const source of charts) {
      source.subscribeCrosshairMove((param) => {
        if (param.time) {
          setHoverValues(getValuesForTime(String(param.time)))
        } else {
          setHoverValues(null)
        }

        if (syncingRef.current) return
        syncingRef.current = true
        if (param.time) {
          snapCrosshair(String(param.time), param.time)
        } else {
          clearOtherCrosshairs(source)
        }
        syncingRef.current = false
      })
    }
  }, [getValuesForTime])

  const setupSingleChartCrosshair = useCallback((chart: IChartApi, series: ReturnType<IChartApi["addSeries"]>) => {
    chart.subscribeCrosshairMove((param) => {
      if (param.time) {
        const key = String(param.time)
        setHoverValues(getValuesForTime(key))
        // Snap crosshair to close price
        if (!syncingRef.current) {
          syncingRef.current = true
          const closeVal = closeByTime.current.get(key)
          if (closeVal !== undefined) {
            chart.setCrosshairPosition(closeVal, param.time, series)
          }
          syncingRef.current = false
        }
      } else {
        setHoverValues(null)
      }
    })
  }, [getValuesForTime])

  return {
    hoverValues,
    buildLookupMaps,
    syncCharts,
    setupSingleChartCrosshair,
  }
}
