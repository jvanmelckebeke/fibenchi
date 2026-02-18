import {
  createChart,
  createSeriesMarkers,
  type IChartApi,
  type Time,
  type ISeriesMarkersPluginApi,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts"
import type { Price, Indicator, Annotation } from "@/lib/api"
import { baseChartOptions } from "@/lib/chart-utils"
import { BandFillPrimitive } from "./bollinger-band-fill"

type Series = ReturnType<IChartApi["addSeries"]>

// ---- Series handle interfaces ----

export interface OverlaySeries {
  sma20: Series
  sma50: Series
  bbUpper: Series
  bbLower: Series
  bbFill: BandFillPrimitive
}

export interface RsiChartState {
  chart: IChartApi
  series: Series
  overbought: Series
  oversold: Series
}

export interface MacdChartState {
  chart: IChartApi
  hist: Series
  line: Series
  signal: Series
  zero: Series
}

export type MarkersHandle = ISeriesMarkersPluginApi<Time>

// ---- Chart creation (structure only, no data) ----

/** Create the main price chart with an empty candle or line series. */
export function createMainChart(
  container: HTMLElement,
  chartType: "candle" | "line",
  height: number,
  hideTimeAxis: boolean,
): { chart: IChartApi; series: Series } {
  const opts = baseChartOptions(container, height)
  const chart = createChart(container, {
    ...opts,
    timeScale: { ...opts.timeScale, visible: !hideTimeAxis },
  })

  const series =
    chartType === "line"
      ? chart.addSeries(LineSeries, {
          color: "#3b82f6",
          lineWidth: 2,
          priceLineVisible: false,
        })
      : chart.addSeries(CandlestickSeries, {
          upColor: "#22c55e",
          downColor: "#ef4444",
          borderUpColor: "#22c55e",
          borderDownColor: "#ef4444",
          wickUpColor: "#22c55e",
          wickDownColor: "#ef4444",
        })

  return { chart, series }
}

/** Create overlay series (SMA20, SMA50, Bollinger Bands) without data. */
export function createOverlaySeries(chart: IChartApi): OverlaySeries {
  const bbLineOpts = {
    color: "rgba(96, 165, 250, 0.4)",
    lineWidth: 1 as const,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  }

  const bbUpper = chart.addSeries(LineSeries, bbLineOpts)
  const bbLower = chart.addSeries(LineSeries, bbLineOpts)
  const bbFill = new BandFillPrimitive([])
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- lightweight-charts plugin API type mismatch
  bbUpper.attachPrimitive(bbFill as any)

  const sma20 = chart.addSeries(LineSeries, {
    color: "#14b8a6",
    lineWidth: 1,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  })

  const sma50 = chart.addSeries(LineSeries, {
    color: "#8b5cf6",
    lineWidth: 1,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  })

  return { sma20, sma50, bbUpper, bbLower, bbFill }
}

/** Create the RSI sub-chart with empty series. */
export function createRsiSubChart(
  container: HTMLElement,
): RsiChartState {
  const rsiOpts = baseChartOptions(container, 120)
  const chart = createChart(container, {
    ...rsiOpts,
    rightPriceScale: {
      ...rsiOpts.rightPriceScale,
      autoScale: false,
      scaleMargins: { top: 0.05, bottom: 0.05 },
    },
  })

  const series = chart.addSeries(LineSeries, {
    color: "#8b5cf6",
    lineWidth: 2,
    priceLineVisible: false,
    autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
  })

  const thresholdOpts = {
    lineWidth: 1 as const,
    lineStyle: 2 as const,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
    autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
  }
  const overbought = chart.addSeries(LineSeries, { ...thresholdOpts, color: "rgba(239, 68, 68, 0.5)" })
  const oversold = chart.addSeries(LineSeries, { ...thresholdOpts, color: "rgba(34, 197, 94, 0.5)" })

  return { chart, series, overbought, oversold }
}

/** Create the MACD sub-chart with empty series. */
export function createMacdSubChart(
  container: HTMLElement,
): MacdChartState {
  const chart = createChart(container, baseChartOptions(container, 120))

  const hist = chart.addSeries(HistogramSeries, { priceLineVisible: false, base: 0 })

  const line = chart.addSeries(LineSeries, {
    color: "#38bdf8",
    lineWidth: 2,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  })

  const signal = chart.addSeries(LineSeries, {
    color: "#fb923c",
    lineWidth: 2,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  })

  const zero = chart.addSeries(LineSeries, {
    color: "rgba(161, 161, 170, 0.3)",
    lineWidth: 1,
    lineStyle: 2,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  })

  return { chart, hist, line, signal, zero }
}

// ---- Data setting functions ----

/** Set price data on the main series. */
export function setMainSeriesData(
  series: Series,
  prices: Price[],
  chartType: "candle" | "line",
): void {
  if (chartType === "line") {
    series.setData(prices.map((p) => ({ time: p.date, value: p.close })))
  } else {
    series.setData(
      prices.map((p) => ({
        time: p.date,
        open: p.open,
        high: p.high,
        low: p.low,
        close: p.close,
      })),
    )
  }
}

/** Set indicator data on overlay series. Hidden overlays get empty data. */
export function setOverlayData(
  overlays: OverlaySeries,
  indicators: Indicator[],
  opts: { sma20: boolean; sma50: boolean; bollinger: boolean },
): void {
  overlays.sma20.setData(
    opts.sma20
      ? indicators.filter((i) => i.values.sma_20 !== null).map((i) => ({ time: i.date, value: i.values.sma_20! }))
      : [],
  )

  overlays.sma50.setData(
    opts.sma50
      ? indicators.filter((i) => i.values.sma_50 !== null).map((i) => ({ time: i.date, value: i.values.sma_50! }))
      : [],
  )

  if (opts.bollinger) {
    const bbData = indicators.filter((i) => i.values.bb_upper !== null && i.values.bb_lower !== null)
    overlays.bbFill.data = bbData.map((i) => ({ time: i.date, upper: i.values.bb_upper!, lower: i.values.bb_lower! }))
    overlays.bbUpper.setData(bbData.map((i) => ({ time: i.date, value: i.values.bb_upper! })))
    overlays.bbLower.setData(bbData.map((i) => ({ time: i.date, value: i.values.bb_lower! })))
  } else {
    overlays.bbFill.data = []
    overlays.bbUpper.setData([])
    overlays.bbLower.setData([])
  }
}

/** Set RSI data on the RSI sub-chart series. */
export function setRsiData(rsi: RsiChartState, indicators: Indicator[]): void {
  const rsiData = indicators.filter((i) => i.values.rsi !== null)
  rsi.series.setData(rsiData.map((i) => ({ time: i.date, value: i.values.rsi! })))

  const dates = rsiData.map((i) => i.date)
  rsi.overbought.setData(dates.length ? dates.map((d) => ({ time: d, value: 70 })) : [])
  rsi.oversold.setData(dates.length ? dates.map((d) => ({ time: d, value: 30 })) : [])
}

/** Set MACD data on the MACD sub-chart series. */
export function setMacdData(macd: MacdChartState, indicators: Indicator[]): void {
  const macdData = indicators.filter((i) => i.values.macd !== null)

  macd.hist.setData(
    macdData.map((i) => ({
      time: i.date,
      value: i.values.macd_hist!,
      color: i.values.macd_hist! >= 0 ? "rgba(34, 197, 94, 0.6)" : "rgba(239, 68, 68, 0.6)",
    })),
  )

  macd.line.setData(macdData.map((i) => ({ time: i.date, value: i.values.macd! })))

  macd.signal.setData(
    indicators.filter((i) => i.values.macd_signal !== null).map((i) => ({ time: i.date, value: i.values.macd_signal! })),
  )

  macd.zero.setData(
    macdData.length ? macdData.map((i) => ({ time: i.date, value: 0 })) : [],
  )
}

/** Create annotation markers on the series. Returns handle for lifecycle management. */
export function addAnnotationMarkers(series: Series, annotations: Annotation[]): MarkersHandle | null {
  if (!annotations.length) return null
  const markers = annotations
    .map((a) => ({
      time: a.date,
      position: "aboveBar" as const,
      color: a.color,
      shape: "circle" as const,
      text: a.title.slice(0, 2),
    }))
    .sort((a, b) => (a.time < b.time ? -1 : 1))
  return createSeriesMarkers(series, markers)
}
