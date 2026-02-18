import { Link } from "react-router-dom"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { IndicatorCell } from "@/components/indicator-cell"
import { formatPrice, formatChangePct } from "@/lib/format"
import { getNumericValue, getStringValue, getHoldingSummaryDescriptors } from "@/lib/indicator-registry"

export interface IndicatorData {
  currency: string
  close: number | null
  change_pct: number | null
  values: Record<string, number | string | null>
}

export interface HoldingsGridRow {
  key: string | number
  symbol: string
  name: string
  percent: number | null
}

interface HoldingsGridProps {
  rows: HoldingsGridRow[]
  indicatorMap: ReadonlyMap<string, IndicatorData>
  indicatorsLoading: boolean
  onRemove?: (key: string | number) => void
  linkTarget?: "_blank"
}

const SUMMARY_DESCRIPTORS = getHoldingSummaryDescriptors()

function buildGridTemplate(hasRemove: boolean): string {
  // base: symbol, name, %, price, chg%
  const base = "4rem 1fr 3.5rem 5rem 4rem"
  const indicatorCols = SUMMARY_DESCRIPTORS.map(() => "3.5rem").join(" ")
  const removePart = hasRemove ? " 2rem" : ""
  return `${base} ${indicatorCols}${removePart}`
}

export function HoldingsGrid({ rows, indicatorMap, indicatorsLoading, onRemove, linkTarget }: HoldingsGridProps) {
  const hasRemove = !!onRemove
  const gridTemplate = buildGridTemplate(hasRemove)
  const gridStyle = { gridTemplateColumns: gridTemplate }

  return (
    <div className="overflow-x-auto">
      <div className={`${hasRemove ? "min-w-[750px]" : "min-w-[700px]"} space-y-0`}>
        <div className="grid text-xs text-muted-foreground border-b border-border pb-1 mb-1 gap-x-2" style={gridStyle}>
          <span>Symbol</span>
          <span>Name</span>
          <span className="text-right">%</span>
          <span className="text-right">Price</span>
          <span className="text-right">Chg%</span>
          {SUMMARY_DESCRIPTORS.map((desc) => (
            <span key={desc.id} className="text-right">{desc.holdingSummary!.label}</span>
          ))}
          {hasRemove && <span></span>}
        </div>
        {rows.map((row) => {
          const ind = indicatorMap.get(row.symbol)
          const chg = formatChangePct(ind?.change_pct ?? null)

          return (
            <div
              key={row.key}
              className={`grid text-sm py-1 hover:bg-muted/50 rounded gap-x-2 items-center${hasRemove ? " group/row" : ""}`}
              style={gridStyle}
            >
              <Link
                to={`/asset/${row.symbol}`}
                {...(linkTarget === "_blank" ? { target: "_blank", rel: "noopener noreferrer" } : {})}
                className="font-mono text-xs text-primary hover:underline"
              >
                {row.symbol}
              </Link>
              <span className="text-muted-foreground truncate text-xs">{row.name}</span>
              <IndicatorCell value={row.percent != null ? `${row.percent.toFixed(1)}%` : null} />
              {indicatorsLoading ? (
                <span className="text-right text-xs text-muted-foreground animate-pulse" style={{ gridColumn: `span ${2 + SUMMARY_DESCRIPTORS.length}` }}>Loading...</span>
              ) : (
                <>
                  <IndicatorCell value={ind?.close != null ? formatPrice(ind.close, ind.currency, 0) : null} />
                  <IndicatorCell value={chg.text} className={chg.className} />
                  {SUMMARY_DESCRIPTORS.map((desc) => {
                    const hs = desc.holdingSummary!
                    return (
                      <HoldingSummaryCell
                        key={desc.id}
                        format={hs.format}
                        field={hs.field}
                        colorMap={hs.colorMap}
                        values={ind?.values}
                        close={ind?.close ?? null}
                      />
                    )
                  })}
                </>
              )}
              {hasRemove && (
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-5 w-5 opacity-0 group-hover/row:opacity-100 transition-opacity"
                  onClick={() => onRemove!(row.key)}
                >
                  <X className="h-3 w-3" />
                </Button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function HoldingSummaryCell({
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
  const colorClass = str != null && colorMap ? (colorMap[str] ?? "") : ""
  const display = str != null ? str.charAt(0).toUpperCase() + str.slice(1) : null
  return <IndicatorCell value={display} className={colorClass} />
}
