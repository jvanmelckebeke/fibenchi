// Shared colour palette for thesis dots and tag swatches (via ColorSwatchPicker),
// so the palette can't drift between pickers. Tailwind 500-level hues,
// rainbow-ordered for a pleasant picker. All eight original presets are retained
// (existing theses keep matching a swatch).
export const THESIS_PRESET_COLORS = [
  "#ef4444", // red
  "#f97316", // orange
  "#f59e0b", // amber
  "#eab308", // yellow
  "#84cc16", // lime
  "#22c55e", // green
  "#10b981", // emerald
  "#14b8a6", // teal
  "#06b6d4", // cyan
  "#0ea5e9", // sky
  "#3b82f6", // blue
  "#6366f1", // indigo
  "#8b5cf6", // violet
  "#a855f7", // purple
  "#d946ef", // fuchsia
  "#ec4899", // pink
  "#f43f5e", // rose
  "#64748b", // slate
  "#78716c", // stone
]

// Default colour for a freshly created thesis (preserves the prior blue default).
export const DEFAULT_THESIS_COLOR = "#3b82f6"
