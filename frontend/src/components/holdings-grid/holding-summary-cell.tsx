import { IndicatorCell } from "@/components/indicator-cell"
import { getNumericValue, getStringValue } from "@/lib/indicator-registry"

export function HoldingSummaryCell({
  format,
  field,
  colorMap,
  values,
  close,
}: {
  format: "numeric" | "compare_close" | "string_map"
  field: string
  colorMap?: Record<string, string>
  values?: Record<string, number | string | null>
  close: number | null
}) {
  if (format === "numeric") {
    const val = getNumericValue(values, field)
    return <IndicatorCell value={val != null ? val.toFixed(0) : null} />
  }

  if (format === "compare_close") {
    const val = getNumericValue(values, field)
    const above = val != null && close != null ? close > val : null
    return (
      <IndicatorCell
        value={above !== null ? (above ? "Above" : "Below") : null}
        className={above === true ? "text-emerald-500" : above === false ? "text-red-500" : ""}
      />
    )
  }

  // string_map
  const str = getStringValue(values, field)
  let colorClass = str != null && colorMap ? (colorMap[str] ?? "") : ""

  // ADX "strong" -> color by direction (+DI vs -DI)
  if (field === "adx_trend" && str === "strong") {
    const plusDi = getNumericValue(values, "plus_di")
    const minusDi = getNumericValue(values, "minus_di")
    if (plusDi != null && minusDi != null) {
      colorClass = plusDi > minusDi ? "text-emerald-500" : "text-red-500"
    }
  }

  const display = str != null ? str.charAt(0).toUpperCase() + str.slice(1) : null
  return <IndicatorCell value={display} className={colorClass} />
}
