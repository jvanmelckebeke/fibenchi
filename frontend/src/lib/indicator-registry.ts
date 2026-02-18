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

export type IndicatorPlacement = "overlay" | "subchart"

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
  color: string
  lineWidth?: number
  type?: "line" | "histogram"
  thresholdColors?: ThresholdColor[]
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
      { field: "bb_upper", label: "BB Upper", color: "rgba(96, 165, 250, 0.4)", lineWidth: 1 },
      { field: "bb_lower", label: "BB Lower", color: "rgba(96, 165, 250, 0.4)", lineWidth: 1 },
    ],
    decimals: 2,
  },
  {
    id: "macd",
    label: "MACD (12,26,9)",
    shortLabel: "MACD",
    placement: "subchart",
    fields: ["macd", "macd_signal", "macd_hist"],
    sortableFields: ["macd", "macd_signal", "macd_hist"],
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
      },
      { field: "macd", label: "MACD", color: "#38bdf8", lineWidth: 2 },
      { field: "macd_signal", label: "Signal", color: "#fb923c", lineWidth: 2 },
    ],
    decimals: 2,
    chartConfig: {
      lines: [{ value: 0, color: "rgba(161, 161, 170, 0.3)" }],
    },
  },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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
  values: Record<string, number | string | null> | undefined,
  field: string,
): number | null {
  const v = values?.[field]
  return typeof v === "number" ? v : null
}

/** Safely extract a string value from the values dict. */
export function getStringValue(
  values: Record<string, number | string | null> | undefined,
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

export function getAllIndicatorFields(): string[] {
  return INDICATOR_REGISTRY.flatMap((d) => d.fields)
}

export function getAllSortableFields(): string[] {
  return INDICATOR_REGISTRY.flatMap((d) => d.sortableFields)
}

export function getDescriptorById(id: string): IndicatorDescriptor | undefined {
  return INDICATOR_REGISTRY.find((d) => d.id === id)
}

export function getSeriesByField(field: string): SeriesDescriptor | undefined {
  for (const desc of INDICATOR_REGISTRY) {
    const s = desc.series.find((ser) => ser.field === field)
    if (s) return s
  }
  return undefined
}
