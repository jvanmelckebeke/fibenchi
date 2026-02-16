import {
  createChart,
  createSeriesMarkers,
  type IChartApi,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
} from "lightweight-charts"
import type { Price, Indicator, Annotation } from "@/lib/api"
import { baseChartOptions } from "@/lib/chart-utils"
import { BandFillPrimitive } from "./bollinger-band-fill"

type Series = ReturnType<IChartApi["addSeries"]>

/** Create the main price series (candle or line) and return both chart and series. */
export function createMainChart(
  container: HTMLElement,
  prices: Price[],
  chartType: "candle" | "line",
  height: number,
  hideTimeAxis: boolean,
): { chart: IChartApi; series: Series } {
  const opts = baseChartOptions(container, height)
  const chart = createChart(container, {
    ...opts,
    timeScale: { ...opts.timeScale, visible: !hideTimeAxis },
  })

  let series: Series
  if (chartType === "line") {
    series = chart.addSeries(LineSeries, {
      color: "#3b82f6",
      lineWidth: 2,
      priceLineVisible: false,
    })
    series.setData(prices.map((p) => ({ time: p.date, value: p.close })))
  } else {
    series = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderUpColor: "#22c55e",
      borderDownColor: "#ef4444",
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    })
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

  return { chart, series }
}

/** Add Bollinger Bands (upper/lower lines + shaded fill) to the chart. */
export function addBollingerBands(chart: IChartApi, indicators: Indicator[]): void {
  const bbData = indicators.filter((i) => i.bb_upper !== null && i.bb_lower !== null)
  if (!bbData.length) return

  const lineOpts = {
    color: "rgba(96, 165, 250, 0.4)",
    lineWidth: 1 as const,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  }

  const bbUpperLine = chart.addSeries(LineSeries, lineOpts)
  bbUpperLine.setData(bbData.map((i) => ({ time: i.date, value: i.bb_upper! })))

  const bbLowerLine = chart.addSeries(LineSeries, lineOpts)
  bbLowerLine.setData(bbData.map((i) => ({ time: i.date, value: i.bb_lower! })))

  const bandFill = new BandFillPrimitive(
    bbData.map((i) => ({ time: i.date, upper: i.bb_upper!, lower: i.bb_lower! })),
  )
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- lightweight-charts plugin API type mismatch
  bbUpperLine.attachPrimitive(bandFill as any)
}

/** Add SMA overlay lines to the chart. */
export function addSmaOverlays(
  chart: IChartApi,
  indicators: Indicator[],
  opts: { sma20: boolean; sma50: boolean },
): void {
  if (opts.sma20) {
    const sma20 = chart.addSeries(LineSeries, {
      color: "#14b8a6",
      lineWidth: 1,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })
    sma20.setData(
      indicators.filter((i) => i.sma_20 !== null).map((i) => ({ time: i.date, value: i.sma_20! })),
    )
  }

  if (opts.sma50) {
    const sma50 = chart.addSeries(LineSeries, {
      color: "#8b5cf6",
      lineWidth: 1,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })
    sma50.setData(
      indicators.filter((i) => i.sma_50 !== null).map((i) => ({ time: i.date, value: i.sma_50! })),
    )
  }
}

/** Add annotation markers to the main series. */
export function addAnnotationMarkers(series: Series, annotations: Annotation[]): void {
  if (!annotations.length) return
  const markers = annotations
    .map((a) => ({
      time: a.date,
      position: "aboveBar" as const,
      color: a.color,
      shape: "circle" as const,
      text: a.title.slice(0, 2),
    }))
    .sort((a, b) => (a.time < b.time ? -1 : 1))
  createSeriesMarkers(series, markers)
}

/** Create the RSI sub-chart and return chart + primary series. */
export function createRsiSubChart(
  container: HTMLElement,
  indicators: Indicator[],
): { chart: IChartApi; series: Series } {
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
  series.setData(
    indicators.filter((i) => i.rsi !== null).map((i) => ({ time: i.date, value: i.rsi! })),
  )

  // Threshold lines (overbought 70, oversold 30)
  const thresholdOpts = {
    lineWidth: 1 as const,
    lineStyle: 2 as const,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
    autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
  }
  const overbought = chart.addSeries(LineSeries, { ...thresholdOpts, color: "rgba(239, 68, 68, 0.5)" })
  const oversold = chart.addSeries(LineSeries, { ...thresholdOpts, color: "rgba(34, 197, 94, 0.5)" })

  const rsiDates = indicators.filter((i) => i.rsi !== null).map((i) => i.date)
  if (rsiDates.length) {
    overbought.setData(rsiDates.map((d) => ({ time: d, value: 70 })))
    oversold.setData(rsiDates.map((d) => ({ time: d, value: 30 })))
  }

  chart.timeScale().fitContent()
  return { chart, series }
}

/** Create the MACD sub-chart and return chart + primary series. */
export function createMacdSubChart(
  container: HTMLElement,
  indicators: Indicator[],
): { chart: IChartApi; series: Series } {
  const chart = createChart(container, baseChartOptions(container, 120))

  const macdData = indicators.filter((i) => i.macd !== null)

  const histSeries = chart.addSeries(HistogramSeries, { priceLineVisible: false, base: 0 })
  histSeries.setData(
    macdData.map((i) => ({
      time: i.date,
      value: i.macd_hist!,
      color: i.macd_hist! >= 0 ? "rgba(34, 197, 94, 0.6)" : "rgba(239, 68, 68, 0.6)",
    })),
  )

  const lineSeries = chart.addSeries(LineSeries, {
    color: "#38bdf8",
    lineWidth: 2,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  })
  lineSeries.setData(macdData.map((i) => ({ time: i.date, value: i.macd! })))

  const signalSeries = chart.addSeries(LineSeries, {
    color: "#fb923c",
    lineWidth: 2,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
  })
  signalSeries.setData(
    indicators.filter((i) => i.macd_signal !== null).map((i) => ({ time: i.date, value: i.macd_signal! })),
  )

  if (macdData.length) {
    const zeroLine = chart.addSeries(LineSeries, {
      color: "rgba(161, 161, 170, 0.3)",
      lineWidth: 1,
      lineStyle: 2,
      priceLineVisible: false,
      crosshairMarkerVisible: false,
    })
    zeroLine.setData(macdData.map((i) => ({ time: i.date, value: 0 })))
  }

  chart.timeScale().fitContent()
  return { chart, series: lineSeries }
}
