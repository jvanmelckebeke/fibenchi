/**
 * Frontend indicator descriptor registry.
 *
 * Declarative definitions for all technical indicators — used by charts,
 * tables, settings, and conditional coloring. Mirrors the backend
 * INDICATOR_REGISTRY but with frontend-specific rendering metadata.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type IndicatorPlacement = "overlay" | "subchart" | "card"

/** Declarative conditional-color rule (pure data, no callbacks). */
export interface ThresholdColor {
  condition: "lt" | "gt" | "lte" | "gte"
  value: number
  className: string
}

/** A single chart series within an indicator (e.g. MACD has 3). */
export interface SeriesDescriptor {
  field: string
  label: string
  /** Color used for the chart line/series. */
  color: string
  /** Opaque color for legend text (falls back to `color`). */
  legendColor?: string
  lineWidth?: number
  type?: "line" | "histogram"
  thresholdColors?: ThresholdColor[]
  /** Histogram bar colors keyed by sign (positive/negative). */
  histogramColors?: { positive: string; negative: string }
}

/** Reference line on a sub-chart (e.g. RSI overbought at 70). */
export interface ThresholdLine {
  value: number
  color: string
}

/** Full descriptor for one indicator group. */
export interface IndicatorDescriptor {
  id: string
  label: string
  shortLabel: string
  placement: IndicatorPlacement
  /** All value-dict fields produced by this indicator. */
  fields: string[]
  /** Fields that can be used for table sorting. */
  sortableFields: string[]
  series: SeriesDescriptor[]
  decimals: number
  /** Sub-chart reference lines and fixed y-axis range. */
  chartConfig?: {
    lines?: ThresholdLine[]
    range?: { min: number; max: number }
  }
  /** Band-fill between two series fields (e.g. Bollinger Bands). */
  bandFill?: { upperField: string; lowerField: string }
  /** How this indicator appears in the holdings grid summary column. */
  holdingSummary?: {
    label: string
    field: string
    format: "numeric" | "compare_close" | "string_map"
    colorMap?: Record<string, string>
  }
  /** When true, this indicator also renders as a card (in addition to its primary placement). */
  cardEligible?: boolean
  /** Override the default crosshair snap target (defaults to series[0].field). */
  snapField?: string
  /** When true, the indicator's values are denominated in the asset's currency (e.g. ATR). */
  priceDenominated?: boolean
}

/** Narrowed descriptor where holdingSummary is guaranteed present. */
export type IndicatorDescriptorWithSummary = IndicatorDescriptor & {
  holdingSummary: NonNullable<IndicatorDescriptor["holdingSummary"]>
}

// ---------------------------------------------------------------------------
// Registry
// ---------------------------------------------------------------------------

export const INDICATOR_REGISTRY: IndicatorDescriptor[] = [
  {
    id: "rsi",
    label: "RSI (14)",
    shortLabel: "RSI",
    placement: "subchart",
    fields: ["rsi"],
    sortableFields: ["rsi"],
    series: [
      {
        field: "rsi",
        label: "RSI",
        color: "#8b5cf6",
        lineWidth: 2,
        thresholdColors: [
          { condition: "gte", value: 70, className: "text-red-500" },
          { condition: "lte", value: 30, className: "text-emerald-500" },
        ],
      },
    ],
    decimals: 0,
    chartConfig: {
      lines: [
        { value: 70, color: "rgba(239, 68, 68, 0.5)" },
        { value: 30, color: "rgba(34, 197, 94, 0.5)" },
      ],
      range: { min: 0, max: 100 },
    },
    holdingSummary: { label: "RSI", field: "rsi", format: "numeric" },
    cardEligible: true,
  },
  {
    id: "sma_20",
    label: "SMA (20)",
    shortLabel: "SMA20",
    placement: "overlay",
    fields: ["sma_20"],
    sortableFields: [],
    series: [
      { field: "sma_20", label: "SMA 20", color: "#14b8a6", lineWidth: 1 },
    ],
    decimals: 2,
    holdingSummary: { label: "SMA20", field: "sma_20", format: "compare_close" },
  },
  {
    id: "sma_50",
    label: "SMA (50)",
    shortLabel: "SMA50",
    placement: "overlay",
    fields: ["sma_50"],
    sortableFields: [],
    series: [
      { field: "sma_50", label: "SMA 50", color: "#8b5cf6", lineWidth: 1 },
    ],
    decimals: 2,
  },
  {
    id: "bb",
    label: "Bollinger Bands",
    shortLabel: "BB",
    placement: "overlay",
    fields: ["bb_upper", "bb_middle", "bb_lower"],
    sortableFields: [],
    series: [
      { field: "bb_upper", label: "BB Upper", color: "rgba(96, 165, 250, 0.4)", legendColor: "#60a5fa", lineWidth: 1 },
      { field: "bb_lower", label: "BB Lower", color: "rgba(96, 165, 250, 0.4)", legendColor: "#60a5fa", lineWidth: 1 },
    ],
    decimals: 2,
    bandFill: { upperField: "bb_upper", lowerField: "bb_lower" },
    holdingSummary: {
      label: "BB",
      field: "bb_position",
      format: "string_map",
      colorMap: { above: "text-red-500", below: "text-emerald-500" },
    },
  },
  {
    id: "macd",
    label: "MACD (12,26,9)",
    shortLabel: "MACD",
    placement: "subchart",
    fields: ["macd", "macd_signal", "macd_hist"],
    sortableFields: ["macd"],
    series: [
      {
        field: "macd_hist",
        label: "Histogram",
        color: "",
        type: "histogram",
        thresholdColors: [
          { condition: "gte", value: 0, className: "text-emerald-400" },
          { condition: "lt", value: 0, className: "text-red-400" },
        ],
        histogramColors: { positive: "rgba(34, 197, 94, 0.6)", negative: "rgba(239, 68, 68, 0.6)" },
      },
      { field: "macd", label: "MACD", color: "#38bdf8", lineWidth: 2 },
      { field: "macd_signal", label: "Signal", color: "#fb923c", lineWidth: 2 },
    ],
    decimals: 2,
    chartConfig: {
      lines: [{ value: 0, color: "rgba(161, 161, 170, 0.3)" }],
    },
    holdingSummary: {
      label: "MACD",
      field: "macd_signal_dir",
      format: "string_map",
      colorMap: { bullish: "text-emerald-500", bearish: "text-red-500" },
    },
    cardEligible: true,
    snapField: "macd",
  },
  {
    id: "atr",
    label: "ATR (14)",
    shortLabel: "ATR",
    placement: "card",
    fields: ["atr"],
    sortableFields: ["atr"],
    series: [
      { field: "atr", label: "ATR", color: "#f97316", lineWidth: 2 },
    ],
    decimals: 2,
    holdingSummary: { label: "ATR", field: "atr", format: "numeric" },
    priceDenominated: true,
  },
  {
    id: "adx",
    label: "ADX (14)",
    shortLabel: "ADX",
    placement: "card",
    fields: ["adx", "plus_di", "minus_di"],
    sortableFields: ["adx"],
    series: [
      {
        field: "adx",
        label: "ADX",
        color: "#06b6d4",
        lineWidth: 2,
        thresholdColors: [
          { condition: "gte", value: 25, className: "text-emerald-500" },
          { condition: "lt", value: 20, className: "text-zinc-400" },
        ],
      },
      { field: "plus_di", label: "+DI", color: "#22c55e", lineWidth: 1 },
      { field: "minus_di", label: "-DI", color: "#ef4444", lineWidth: 1 },
    ],
    decimals: 1,
    chartConfig: {
      lines: [
        { value: 25, color: "rgba(34, 197, 94, 0.4)" },
        { value: 20, color: "rgba(161, 161, 170, 0.3)" },
      ],
      range: { min: 0, max: 60 },
    },
    holdingSummary: {
      label: "ADX",
      field: "adx_trend",
      format: "string_map",
      colorMap: { strong: "text-emerald-500", weak: "text-yellow-500", absent: "text-zinc-400" },
    },
  },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Check whether an indicator is visible in a visibility map (opt-out model: missing = visible). */
export function isIndicatorVisible(
  visibilityMap: Record<string, boolean> | undefined,
  key: string,
): boolean {
  return visibilityMap?.[key] !== false
}

/** Resolve the first matching threshold color class for a value. */
export function resolveThresholdColor(
  thresholds: ThresholdColor[] | undefined,
  value: number | string | null | undefined,
): string {
  if (!thresholds || value == null) return ""
  const n = typeof value === "number" ? value : parseFloat(String(value))
  if (isNaN(n)) return ""
  for (const t of thresholds) {
    switch (t.condition) {
      case "lt":  if (n < t.value) return t.className; break
      case "gt":  if (n > t.value) return t.className; break
      case "lte": if (n <= t.value) return t.className; break
      case "gte": if (n >= t.value) return t.className; break
    }
  }
  return ""
}

/** Safely extract a numeric value from the values dict. */
export function getNumericValue(
  values: Record<string, number | string | null | undefined> | undefined,
  field: string,
): number | null {
  const v = values?.[field]
  return typeof v === "number" ? v : null
}

/** Safely extract a string value from the values dict. */
export function getStringValue(
  values: Record<string, number | string | null | undefined> | undefined,
  field: string,
): string | null {
  const v = values?.[field]
  return typeof v === "string" ? v : null
}

export function getOverlayDescriptors(): IndicatorDescriptor[] {
  return INDICATOR_REGISTRY.filter((d) => d.placement === "overlay")
}

export function getSubChartDescriptors(): IndicatorDescriptor[] {
  return INDICATOR_REGISTRY.filter((d) => d.placement === "subchart")
}

export function getCardDescriptors(excludeSubcharts = false): IndicatorDescriptor[] {
  return INDICATOR_REGISTRY.filter((d) =>
    d.placement === "card" || (!excludeSubcharts && d.cardEligible),
  )
}

export function getAllIndicatorFields(): string[] {
  return INDICATOR_REGISTRY.flatMap((d) => d.fields)
}

export function getAllSortableFields(): string[] {
  return INDICATOR_REGISTRY.flatMap((d) => d.sortableFields)
}

export function getDescriptorById(id: string): IndicatorDescriptor | undefined {
  return INDICATOR_REGISTRY.find((d) => d.id === id)
}

export function getHoldingSummaryDescriptors(): IndicatorDescriptorWithSummary[] {
  return INDICATOR_REGISTRY.filter(
    (d): d is IndicatorDescriptorWithSummary => d.holdingSummary != null,
  )
}

/** Build sort options from registry: base fields + all sortable indicator fields. */
export function buildSortOptions(): [string, string][] {
  const base: [string, string][] = [
    ["name", "Name"],
    ["price", "Price"],
    ["change_pct", "Change %"],
  ]
  for (const desc of INDICATOR_REGISTRY) {
    for (const field of desc.sortableFields) {
      const series = desc.series.find((s) => s.field === field)
      base.push([field, series?.label ?? field])
    }
  }
  return base
}

/** Extract the three MACD values from an indicator values dict. */
export function extractMacdValues(values?: Record<string, number | string | null>) {
  return values ? {
    macd: getNumericValue(values, "macd"),
    macd_signal: getNumericValue(values, "macd_signal"),
    macd_hist: getNumericValue(values, "macd_hist"),
  } : undefined
}

export function getSeriesByField(field: string): SeriesDescriptor | undefined {
  for (const desc of INDICATOR_REGISTRY) {
    const s = desc.series.find((ser) => ser.field === field)
    if (s) return s
  }
  return undefined
}

/**
 * Resolve the ADX color class based on trend strength + DI direction.
 *
 * - ADX < 20  → gray (no meaningful trend)
 * - ADX 20-25 → yellow (emerging trend)
 * - ADX >= 25 → green (+DI > -DI, bullish) or red (-DI > +DI, bearish)
 */
export function resolveAdxColor(
  adx: number,
  values: Record<string, number | string | null | undefined>,
): string {
  if (adx < 20) return "text-zinc-400"
  if (adx < 25) return "text-yellow-500"
  const plusDi = getNumericValue(values, "plus_di")
  const minusDi = getNumericValue(values, "minus_di")
  if (plusDi != null && minusDi != null) {
    return plusDi > minusDi ? "text-emerald-500" : "text-red-500"
  }
  return "text-foreground"
}
