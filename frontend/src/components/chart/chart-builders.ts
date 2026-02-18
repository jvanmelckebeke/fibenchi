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
import {
  getOverlayDescriptors,
  getDescriptorById,
  type IndicatorDescriptor,
  type SeriesDescriptor,
} from "@/lib/indicator-registry"

type Series = ReturnType<IChartApi["addSeries"]>

// ---- Generic state interfaces ----

export interface OverlayState {
  /** Map from field name → chart series handle. */
  seriesMap: Map<string, Series>
  /** Band-fill primitives (e.g. Bollinger fill). */
  bandFills: { descriptor: IndicatorDescriptor; fill: BandFillPrimitive; upperSeries: Series }[]
}

export interface SubChartState {
  chart: IChartApi
  descriptorId: string
  /** Map from field name → chart series handle. */
  seriesMap: Map<string, Series>
  /** Threshold/reference line series (e.g. RSI overbought/oversold). */
  thresholdSeries: Series[]
  /** Field used for crosshair y-snap. */
  snapField: string
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

/** Create overlay series for all overlay descriptors from the registry. */
export function createOverlays(chart: IChartApi): OverlayState {
  const seriesMap = new Map<string, Series>()
  const bandFills: OverlayState["bandFills"] = []

  for (const desc of getOverlayDescriptors()) {
    // Create chart series for each series entry
    for (const s of desc.series) {
      const handle = chart.addSeries(LineSeries, {
        color: s.color,
        lineWidth: (s.lineWidth ?? 1) as 1 | 2 | 3 | 4,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
      })
      seriesMap.set(s.field, handle)
    }

    // Attach band-fill primitive if descriptor specifies one
    if (desc.bandFill) {
      const upperSeries = seriesMap.get(desc.bandFill.upperField)
      if (upperSeries) {
        const fill = new BandFillPrimitive([])
        // eslint-disable-next-line @typescript-eslint/no-explicit-any -- lightweight-charts plugin API type mismatch
        upperSeries.attachPrimitive(fill as any)
        bandFills.push({ descriptor: desc, fill, upperSeries })
      }
    }
  }

  return { seriesMap, bandFills }
}

/** Create a generic sub-chart from an indicator descriptor. */
export function createSubChart(
  container: HTMLElement,
  descriptor: IndicatorDescriptor,
): SubChartState {
  const hasFixedRange = !!descriptor.chartConfig?.range
  const opts = baseChartOptions(container, 120)
  const chart = createChart(container, {
    ...opts,
    ...(hasFixedRange && {
      rightPriceScale: {
        ...opts.rightPriceScale,
        autoScale: false,
        scaleMargins: { top: 0.05, bottom: 0.05 },
      },
    }),
  })

  const range = descriptor.chartConfig?.range
  const autoscaleProvider = range
    ? () => ({ priceRange: { minValue: range.min, maxValue: range.max } })
    : undefined

  const seriesMap = new Map<string, Series>()

  for (const s of descriptor.series) {
    const handle = createSeriesFromDescriptor(chart, s, autoscaleProvider)
    seriesMap.set(s.field, handle)
  }

  // Create threshold/reference line series
  const thresholdSeries: Series[] = []
  if (descriptor.chartConfig?.lines) {
    for (const line of descriptor.chartConfig.lines) {
      const handle = chart.addSeries(LineSeries, {
        color: line.color,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        crosshairMarkerVisible: false,
        ...(autoscaleProvider && { autoscaleInfoProvider: autoscaleProvider }),
      })
      thresholdSeries.push(handle)
    }
  }

  // Snap field = first data series field
  const snapField = descriptor.series[0]?.field ?? descriptor.fields[0]

  return { chart, descriptorId: descriptor.id, seriesMap, thresholdSeries, snapField }
}

function createSeriesFromDescriptor(
  chart: IChartApi,
  s: SeriesDescriptor,
  autoscaleProvider?: () => { priceRange: { minValue: number; maxValue: number } },
): Series {
  if (s.type === "histogram") {
    return chart.addSeries(HistogramSeries, {
      priceLineVisible: false,
      base: 0,
      ...(autoscaleProvider && { autoscaleInfoProvider: autoscaleProvider }),
    })
  }

  return chart.addSeries(LineSeries, {
    color: s.color,
    lineWidth: (s.lineWidth ?? 2) as 1 | 2 | 3 | 4,
    priceLineVisible: false,
    crosshairMarkerVisible: false,
    ...(autoscaleProvider && { autoscaleInfoProvider: autoscaleProvider }),
  })
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

/** Set overlay data for all overlay descriptors. Disabled overlays get empty data. */
export function setAllOverlayData(
  state: OverlayState,
  indicators: Indicator[],
  enabledIds: Set<string>,
): void {
  for (const desc of getOverlayDescriptors()) {
    const enabled = enabledIds.has(desc.id)

    for (const s of desc.series) {
      const handle = state.seriesMap.get(s.field)
      if (!handle) continue
      handle.setData(
        enabled
          ? indicators
              .filter((i) => i.values[s.field] !== null)
              .map((i) => ({ time: i.date, value: i.values[s.field]! }))
          : [],
      )
    }

    // Band fill
    if (desc.bandFill) {
      const bandEntry = state.bandFills.find((bf) => bf.descriptor.id === desc.id)
      if (bandEntry) {
        if (enabled) {
          const { upperField, lowerField } = desc.bandFill
          const data = indicators.filter(
            (i) => i.values[upperField] !== null && i.values[lowerField] !== null,
          )
          bandEntry.fill.data = data.map((i) => ({
            time: i.date,
            upper: i.values[upperField]!,
            lower: i.values[lowerField]!,
          }))
        } else {
          bandEntry.fill.data = []
        }
      }
    }
  }
}

/** Set data on a sub-chart from its descriptor's series definitions. */
export function setSubChartData(state: SubChartState, indicators: Indicator[]): void {
  const desc = getDescriptorById(state.descriptorId)
  if (!desc) return

  // Collect date range from the first series that has data
  let dates: string[] = []

  for (const s of desc.series) {
    const handle = state.seriesMap.get(s.field)
    if (!handle) continue

    const filtered = indicators.filter((i) => i.values[s.field] !== null)

    if (s.type === "histogram" && s.histogramColors) {
      handle.setData(
        filtered.map((i) => ({
          time: i.date,
          value: i.values[s.field]!,
          color: i.values[s.field]! >= 0 ? s.histogramColors!.positive : s.histogramColors!.negative,
        })),
      )
    } else {
      handle.setData(filtered.map((i) => ({ time: i.date, value: i.values[s.field]! })))
    }

    if (dates.length === 0 && filtered.length > 0) {
      dates = filtered.map((i) => i.date)
    }
  }

  // Set threshold line data over the date range
  if (desc.chartConfig?.lines && dates.length > 0) {
    desc.chartConfig.lines.forEach((line, idx) => {
      const handle = state.thresholdSeries[idx]
      if (handle) {
        handle.setData(dates.map((d) => ({ time: d, value: line.value })))
      }
    })
  }
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
