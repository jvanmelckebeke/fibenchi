/**
 * Declarative indicator descriptor data.
 *
 * Pure configuration — no logic. Each entry defines how one indicator
 * appears across charts, tables, cards, and the holdings grid.
 * Add new indicators here; helpers live in indicator-registry.ts.
 */

import type { IndicatorDescriptor } from "./indicator-registry"

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
    id: "atr_pct",
    label: "ATR%",
    shortLabel: "ATR%",
    placement: "card",
    fields: ["atr_pct"],
    sortableFields: ["atr_pct"],
    series: [
      {
        field: "atr_pct",
        label: "ATR%",
        color: "#f97316",
        lineWidth: 2,
      },
    ],
    decimals: 2,
    suffix: "%",
    holdingSummary: { label: "ATR%", field: "atr_pct", format: "numeric" },
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
  {
    id: "volume",
    label: "Volume",
    shortLabel: "Vol",
    placement: "card",
    fields: ["volume", "avg_volume"],
    sortableFields: ["volume", "avg_volume"],
    series: [
      { field: "volume", label: "Vol", color: "#64748b" },
      { field: "avg_volume", label: "Avg Vol", color: "#94a3b8" },
    ],
    decimals: 0,
    compactFormat: true,
  },
]
