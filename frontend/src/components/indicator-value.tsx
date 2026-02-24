import {
  resolveThresholdColor,
  resolveAdxColor,
  getNumericValue,
  type IndicatorDescriptor,
} from "@/lib/indicator-registry"
import { currencySymbol } from "@/lib/format"

// ---------------------------------------------------------------------------
// Shared indicator value display
// ---------------------------------------------------------------------------

/**
 * Renders the numeric value (with color, currency prefix, and optional
 * sub-value rows) for a single indicator descriptor. Used by both the
 * detail-page indicator cards and the dashboard mini-indicator cards.
 *
 * This component renders **only** the value portion — callers provide their
 * own container, label, and interaction affordances.
 */
export function IndicatorValue({
  descriptor,
  values,
  currency,
  compact,
}: {
  descriptor: IndicatorDescriptor
  values?: Record<string, number | string | null | undefined>
  currency?: string
  compact?: boolean
}) {
  const mainSeries = descriptor.series[0]
  const mainVal = getNumericValue(values, mainSeries.field)
  const sizeClass = compact ? "text-sm" : "text-2xl"

  if (mainVal == null) {
    return (
      <div className="flex flex-col">
        <span className={`${sizeClass} font-semibold tabular-nums text-muted-foreground`}>
          --
        </span>
      </div>
    )
  }

  const colorClass =
    descriptor.id === "adx"
      ? resolveAdxColor(mainVal, values ?? {})
      : resolveThresholdColor(mainSeries.thresholdColors, mainVal)

  const subSize = compact ? "text-[10px]" : "text-xs"
  const subGap = compact ? "gap-2" : "gap-3"

  return (
    <div className="flex flex-col">
      <span
        className={`${sizeClass} font-semibold tabular-nums ${colorClass || "text-foreground"}`}
      >
        {currency && descriptor.priceDenominated ? currencySymbol(currency) : ""}
        {mainVal.toFixed(descriptor.decimals)}{descriptor.suffix ?? ""}
      </span>

      {/* ADX: show +DI / -DI below the main value */}
      {descriptor.id === "adx" && (
        <div className={`flex ${subGap} tabular-nums mt-0.5 ${subSize}`}>
          <span className="text-emerald-500">
            +DI {getNumericValue(values, "plus_di")?.toFixed(1) ?? "--"}
          </span>
          <span className="text-red-500">
            -DI {getNumericValue(values, "minus_di")?.toFixed(1) ?? "--"}
          </span>
        </div>
      )}

      {/* MACD: show line + signal below histogram */}
      {descriptor.id === "macd" && (
        <div className={`flex ${subGap} tabular-nums mt-0.5 ${subSize}`}>
          <span className="text-sky-400">
            <span className="text-muted-foreground">MACD</span> {getNumericValue(values, "macd")?.toFixed(2) ?? "--"}
          </span>
          <span className="text-orange-400">
            <span className="text-muted-foreground">Sig</span> {getNumericValue(values, "macd_signal")?.toFixed(2) ?? "--"}
          </span>
        </div>
      )}
    </div>
  )
}
