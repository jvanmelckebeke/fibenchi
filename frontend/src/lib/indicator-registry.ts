/**
 * Frontend indicator registry — types, helpers, and re-exported data.
 *
 * Descriptor data lives in indicator-descriptors.ts; this file owns the
 * types and all helper functions that operate on the registry.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type IndicatorPlacement = "overlay" | "subchart" | "card"

export type IndicatorCategory = "technical" | "volatility" | "fundamentals" | "market_data"

export const CATEGORY_ORDER: IndicatorCategory[] = ["fundamentals", "market_data", "technical", "volatility"]
export const CATEGORY_LABELS: Record<IndicatorCategory, string> = {
  fundamentals: "Fundamentals",
  market_data: "Market Data",
  technical: "Technical",
  volatility: "Volatility",
}

/** Where an indicator can appear across the UI. */
export type Placement =
  | "group_table"
  | "group_card"
  | "detail_chart"
  | "detail_card"
  | "detail_stats"

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
  description: string
  category: IndicatorCategory
  placement: IndicatorPlacement
  /** UI locations this indicator can appear in. */
  capabilities: Placement[]
  /** UI locations enabled by default (subset of capabilities). */
  defaults: Placement[]
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
  /** Suffix appended after the formatted value (e.g. "%" for ATR%). */
  suffix?: string
  /** When true, table values use formatCompactNumber (K/M/B) instead of toFixed. */
  compactFormat?: boolean
}

/** Narrowed descriptor where holdingSummary is guaranteed present. */
export type IndicatorDescriptorWithSummary = IndicatorDescriptor & {
  holdingSummary: NonNullable<IndicatorDescriptor["holdingSummary"]>
}

// ---------------------------------------------------------------------------
// Registry (re-exported from descriptor data file)
// ---------------------------------------------------------------------------

import { INDICATOR_REGISTRY } from "./indicator-descriptors"
import { currencySymbol, formatCompactNumber } from "./format"
export { INDICATOR_REGISTRY }

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Check whether an indicator is visible at a specific placement.
 * Missing from map → falls back to the descriptor's defaults.
 * Checks capabilities to prevent showing at unsupported placements.
 */
export function isVisibleAt(
  visibilityMap: Record<string, Placement[]> | undefined,
  indicatorId: string,
  placement: Placement,
): boolean {
  const descriptor = getDescriptorById(indicatorId)
  if (!descriptor) return false
  if (!descriptor.capabilities.includes(placement)) return false
  if (!visibilityMap || !(indicatorId in visibilityMap)) {
    return descriptor.defaults.includes(placement)
  }
  return visibilityMap[indicatorId].includes(placement)
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

export function getScannableDescriptors(): IndicatorDescriptor[] {
  return INDICATOR_REGISTRY.filter((d) => d.placement !== "overlay" && d.series.length > 0)
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

export function getDescriptorByField(field: string): IndicatorDescriptor | undefined {
  return INDICATOR_REGISTRY.find((d) => d.fields.includes(field))
}

export function getSeriesByField(field: string): SeriesDescriptor | undefined {
  for (const desc of INDICATOR_REGISTRY) {
    const s = desc.series.find((ser) => ser.field === field)
    if (s) return s
  }
  return undefined
}

/**
 * Format a single indicator field value with the correct prefix, decimals,
 * suffix, and color class. Shared by StatsPanel, IndicatorValue, and any
 * other site that renders a formatted indicator value.
 */
export function formatIndicatorField(
  field: string,
  descriptor: IndicatorDescriptor,
  values: Record<string, number | string | null | undefined>,
  currency?: string,
): { text: string; colorClass: string } {
  const val = getNumericValue(values, field)
  if (val == null) return { text: "--", colorClass: "text-muted-foreground" }

  let text: string
  if (descriptor.compactFormat) {
    text = formatCompactNumber(val)
  } else {
    const prefix = currency && descriptor.priceDenominated ? currencySymbol(currency) : ""
    text = `${prefix}${val.toFixed(descriptor.decimals)}${descriptor.suffix ?? ""}`
  }

  let colorClass: string
  if (descriptor.id === "adx" && field === "adx") {
    colorClass = resolveAdxColor(val, values)
  } else {
    const series = getSeriesByField(field)
    colorClass = resolveThresholdColor(series?.thresholdColors, val) || "text-foreground"
  }

  return { text, colorClass }
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
