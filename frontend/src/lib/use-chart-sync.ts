import { useRef, useState, useCallback } from "react"
import type { IChartApi } from "lightweight-charts"
import type { Price, Indicator } from "@/lib/api"
import type { LegendValues } from "@/components/chart/chart-legends"

export interface ChartEntry {
  chart: IChartApi
  series: ReturnType<IChartApi["addSeries"]>
}

export function useChartSync() {
  const [hoverValues, setHoverValues] = useState<LegendValues | null>(null)

  const closeByTime = useRef(new Map<string, number>())
  const ohlcByTime = useRef(new Map<string, { o: number; h: number; l: number; c: number }>())
  const sma20ByTime = useRef(new Map<string, number>())
  const sma50ByTime = useRef(new Map<string, number>())
  const bbUpperByTime = useRef(new Map<string, number>())
  const bbLowerByTime = useRef(new Map<string, number>())
  const rsiByTime = useRef(new Map<string, number>())
  const macdByTime = useRef(new Map<string, number>())
  const macdSignalByTime = useRef(new Map<string, number>())
  const macdHistByTime = useRef(new Map<string, number>())

  const syncingRef = useRef(false)

  const buildLookupMaps = useCallback((prices: Price[], indicators: Indicator[]) => {
    closeByTime.current.clear()
    ohlcByTime.current.clear()
    sma20ByTime.current.clear()
    sma50ByTime.current.clear()
    bbUpperByTime.current.clear()
    bbLowerByTime.current.clear()
    rsiByTime.current.clear()
    macdByTime.current.clear()
    macdSignalByTime.current.clear()
    macdHistByTime.current.clear()

    for (const p of prices) {
      closeByTime.current.set(p.date, p.close)
      ohlcByTime.current.set(p.date, { o: p.open, h: p.high, l: p.low, c: p.close })
    }
    for (const i of indicators) {
      const v = i.values
      if (v.sma_20 != null) sma20ByTime.current.set(i.date, v.sma_20)
      if (v.sma_50 != null) sma50ByTime.current.set(i.date, v.sma_50)
      if (v.bb_upper != null) bbUpperByTime.current.set(i.date, v.bb_upper)
      if (v.bb_lower != null) bbLowerByTime.current.set(i.date, v.bb_lower)
      if (v.rsi != null) rsiByTime.current.set(i.date, v.rsi)
      if (v.macd != null) macdByTime.current.set(i.date, v.macd)
      if (v.macd_signal != null) macdSignalByTime.current.set(i.date, v.macd_signal)
      if (v.macd_hist != null) macdHistByTime.current.set(i.date, v.macd_hist)
    }
  }, [])

  const getValuesForTime = useCallback((key: string): LegendValues => {
    const ohlc = ohlcByTime.current.get(key)
    return {
      o: ohlc?.o,
      h: ohlc?.h,
      l: ohlc?.l,
      c: ohlc?.c,
      sma20: sma20ByTime.current.get(key),
      sma50: sma50ByTime.current.get(key),
      bbUpper: bbUpperByTime.current.get(key),
      bbLower: bbLowerByTime.current.get(key),
      rsi: rsiByTime.current.get(key),
      macd: macdByTime.current.get(key),
      macdSignal: macdSignalByTime.current.get(key),
      macdHist: macdHistByTime.current.get(key),
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
        const closeVal = closeByTime.current.get(key)
        const rsiVal = rsiByTime.current.get(key)
        const macdVal = macdByTime.current.get(key)

        if (entry === chartEntries[0] && closeVal !== undefined) {
          entry.chart.setCrosshairPosition(closeVal, time, entry.series)
        } else if (chartEntries.length > 1 && entry === chartEntries[1]) {
          const val = rsiVal !== undefined ? rsiVal : macdVal
          if (val !== undefined) entry.chart.setCrosshairPosition(val, time, entry.series)
        } else if (chartEntries.length > 2 && entry === chartEntries[2] && macdVal !== undefined) {
          entry.chart.setCrosshairPosition(macdVal, time, entry.series)
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
        const ohlc = ohlcByTime.current.get(key)
        setHoverValues({
          o: ohlc?.o,
          h: ohlc?.h,
          l: ohlc?.l,
          c: ohlc?.c,
          sma20: sma20ByTime.current.get(key),
          sma50: sma50ByTime.current.get(key),
          bbUpper: bbUpperByTime.current.get(key),
          bbLower: bbLowerByTime.current.get(key),
        })
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
  }, [])

  return {
    hoverValues,
    buildLookupMaps,
    syncCharts,
    setupSingleChartCrosshair,
  }
}
