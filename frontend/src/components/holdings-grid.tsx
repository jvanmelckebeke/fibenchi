import { Link } from "react-router-dom"
import { X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { IndicatorCell } from "@/components/indicator-cell"
import { formatPrice, formatChangePct } from "@/lib/format"

export interface IndicatorData {
  currency: string
  close: number | null
  change_pct: number | null
  rsi: number | null
  sma_20: number | null
  macd: number | null
  macd_signal: number | null
  macd_hist: number | null
  macd_signal_dir: string | null
  bb_upper: number | null
  bb_middle: number | null
  bb_lower: number | null
  bb_position: string | null
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

const GRID_COLS = "grid-cols-[4rem_1fr_3.5rem_5rem_4rem_3.5rem_3.5rem_4rem_3.5rem]"
const GRID_COLS_REMOVABLE = "grid-cols-[4rem_1fr_3.5rem_5rem_4rem_3.5rem_3.5rem_4rem_3.5rem_2rem]"

export function HoldingsGrid({ rows, indicatorMap, indicatorsLoading, onRemove, linkTarget }: HoldingsGridProps) {
  const hasRemove = !!onRemove
  const gridCols = hasRemove ? GRID_COLS_REMOVABLE : GRID_COLS

  return (
    <div className="overflow-x-auto">
      <div className={`${hasRemove ? "min-w-[750px]" : "min-w-[700px]"} space-y-0`}>
        <div className={`grid ${gridCols} text-xs text-muted-foreground border-b border-border pb-1 mb-1 gap-x-2`}>
          <span>Symbol</span>
          <span>Name</span>
          <span className="text-right">%</span>
          <span className="text-right">Price</span>
          <span className="text-right">Chg%</span>
          <span className="text-right">RSI</span>
          <span className="text-right">SMA20</span>
          <span className="text-right">MACD</span>
          <span className="text-right">BB</span>
          {hasRemove && <span></span>}
        </div>
        {rows.map((row) => {
          const ind = indicatorMap.get(row.symbol)
          const chg = formatChangePct(ind?.change_pct ?? null)
          const rsiVal = ind?.rsi
          const rsiColor = rsiVal != null ? (rsiVal > 70 ? "text-red-500" : rsiVal < 30 ? "text-emerald-500" : "") : ""
          const smaAbove = ind?.sma_20 != null && ind?.close != null ? ind.close > ind.sma_20 : null
          const macdDir = ind?.macd_signal_dir
          const bbPos = ind?.bb_position

          return (
            <div
              key={row.key}
              className={`grid ${gridCols} text-sm py-1 hover:bg-muted/50 rounded gap-x-2 items-center${hasRemove ? " group/row" : ""}`}
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
                <span className="col-span-6 text-right text-xs text-muted-foreground animate-pulse">Loading...</span>
              ) : (
                <>
                  <IndicatorCell value={ind?.close != null ? formatPrice(ind.close, ind.currency, 0) : null} />
                  <IndicatorCell value={chg.text} className={chg.className} />
                  <IndicatorCell value={rsiVal != null ? rsiVal.toFixed(0) : null} className={rsiColor} />
                  <IndicatorCell
                    value={smaAbove !== null ? (smaAbove ? "Above" : "Below") : null}
                    className={smaAbove === true ? "text-emerald-500" : smaAbove === false ? "text-red-500" : ""}
                  />
                  <IndicatorCell
                    value={macdDir != null ? (macdDir === "bullish" ? "Bull" : "Bear") : null}
                    className={macdDir === "bullish" ? "text-emerald-500" : macdDir === "bearish" ? "text-red-500" : ""}
                  />
                  <IndicatorCell
                    value={bbPos != null ? bbPos.charAt(0).toUpperCase() + bbPos.slice(1) : null}
                    className={bbPos === "above" ? "text-red-500" : bbPos === "below" ? "text-emerald-500" : ""}
                  />
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
